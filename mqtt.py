#!/usr/bin/python3
# -*- coding: utf-8 -*-
#

import json
import re
import socket
import threading
import time

try:
    from config import MyLog
    import paho.mqtt.client as paho
except Exception as e1:
    import sys
    print("\n\nThis program requires paho-mqtt and config modules.\n")
    print("Error: " + str(e1))
    sys.exit(2)


TOPIC_PREFIX = "somfy"
AVAILABILITY_TOPIC = TOPIC_PREFIX + "/bridge/availability"


def _local_ip():
    """Detect the local IP address used to reach the network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _slugify(text):
    """Convert text to a snake_case slug for HA entity IDs."""
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


class DiscoveryMsg:
    """Home Assistant MQTT discovery payload for a cover entity.

    Follows the HA 2024.x+ MQTT Cover schema with separate command,
    set_position, position, and state topics, LWT-based availability,
    and proper device registry entries linked to the bridge via via_device.
    """

    def __init__(self, shutter_name, shutter_id, bridge_id, web_url=None):
        display_name = shutter_name.replace('_', ' ').title()
        slug = _slugify(shutter_name)

        self.topic = "homeassistant/cover/" + bridge_id + "_" + shutter_id + "/config"

        self.payload = {
            "name": display_name,
            "object_id": slug,
            "unique_id": bridge_id + "_" + shutter_id,
            "device_class": "shutter",

            # Command topics (HA -> Pi-Somfy)
            "command_topic": TOPIC_PREFIX + "/" + shutter_id + "/command",
            "set_position_topic": TOPIC_PREFIX + "/" + shutter_id + "/set_position",

            # Position topic (Pi-Somfy -> HA)
            "position_topic": TOPIC_PREFIX + "/" + shutter_id + "/position",
            "state_topic": TOPIC_PREFIX + "/" + shutter_id + "/state",

            # Command payloads
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",

            # State payloads
            "state_open": "open",
            "state_opening": "opening",
            "state_closing": "closing",
            "state_closed": "closed",
            "state_stopped": "stopped",

            # Position range (0 = fully closed, 100 = fully open)
            "position_open": 100,
            "position_closed": 0,

            # Availability via Last Will and Testament
            "availability": {
                "topic": AVAILABILITY_TOPIC,
                "payload_available": "online",
                "payload_not_available": "offline"
            },

            # Device registry entry
            "device": {
                "identifiers": [bridge_id + "_" + shutter_id],
                "name": "Somfy " + display_name,
                "model": "RTS Shutter",
                "manufacturer": "Somfy",
                "via_device": bridge_id
            }
        }

        if web_url:
            self.payload["device"]["configuration_url"] = web_url

    def json(self):
        return json.dumps(self.payload)


class BridgeDiscoveryMsg:
    """Home Assistant MQTT discovery payload for the Pi-Somfy bridge.

    Registers a connectivity binary_sensor so the bridge appears as a
    parent device. Individual shutters link here via 'via_device'.
    """

    def __init__(self, bridge_id, web_url=None):
        self.topic = "homeassistant/binary_sensor/" + bridge_id + "/connectivity/config"

        self.payload = {
            "name": "Connectivity",
            "object_id": bridge_id + "_connectivity",
            "unique_id": bridge_id + "_connectivity",
            "device_class": "connectivity",
            "entity_category": "diagnostic",
            "state_topic": AVAILABILITY_TOPIC,
            "payload_on": "online",
            "payload_off": "offline",
            "availability": {
                "topic": AVAILABILITY_TOPIC,
                "payload_available": "online",
                "payload_not_available": "offline"
            },
            "device": {
                "identifiers": [bridge_id],
                "name": "Pi-Somfy Bridge",
                "model": "Pi-Somfy RTS Gateway",
                "manufacturer": "Nickduino"
            }
        }

        if web_url:
            self.payload["device"]["configuration_url"] = web_url

    def json(self):
        return json.dumps(self.payload)


class MQTT(threading.Thread, MyLog):

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        threading.Thread.__init__(self, group=group, target=target, name="MQTT")
        self.shutdown_flag = threading.Event()
        self.connected_flag = False
        self.t = None
        self.args = args
        self.kwargs = kwargs
        if kwargs["log"] is not None:
            self.log = kwargs["log"]
        if kwargs["shutter"] is not None:
            self.shutter = kwargs["shutter"]
        if kwargs["config"] is not None:
            self.config = kwargs["config"]

        self.bridge_id = _slugify(self.config.MQTT_ClientID)
        self._web_url = self._detect_web_url()

    def _detect_web_url(self):
        """Build the Pi-Somfy web UI URL for HA device configuration link."""
        try:
            ip = _local_ip()
            if ip:
                port = getattr(self.config, 'HTTPPort', 80)
                return "http://" + ip + ":" + str(port)
        except Exception:
            pass
        return None

    def receiveMessageFromMQTT(self, client, userdata, message):
        try:
            msg = str(message.payload.decode("utf-8"))
            topic = message.topic
            self.LogInfo("MQTT received: " + topic + " = " + msg)

            parts = topic.split("/")
            # Expected: somfy/{shutterId}/command  or  somfy/{shutterId}/set_position
            if len(parts) != 3 or parts[0] != TOPIC_PREFIX:
                self.LogError("Unexpected topic format: " + topic)
                return

            shutter_id = parts[1]
            action = parts[2]

            if action == "command":
                if msg == "OPEN":
                    self.shutter.rise(shutter_id)
                elif msg == "CLOSE":
                    self.shutter.lower(shutter_id)
                elif msg == "STOP":
                    self.shutter.stop(shutter_id)
                else:
                    self.LogError("Unknown command payload: " + msg)

            elif action == "set_position":
                target = int(msg)
                current = self.shutter.getPosition(shutter_id)
                if target >= 100:
                    self.shutter.rise(shutter_id)
                elif target <= 0:
                    self.shutter.lower(shutter_id)
                elif target > current:
                    self.shutter.risePartial(shutter_id, target)
                elif target < current:
                    self.shutter.lowerPartial(shutter_id, target)

            else:
                self.LogError("Unknown topic action: " + topic)

        except Exception as e:
            self.LogError("Exception in receiveMessageFromMQTT: " + str(e))

    def _publish_state(self, shutter_id, state):
        """Publish a cover state (open/closed/opening/closing/stopped)."""
        self.sendMQTT(TOPIC_PREFIX + "/" + shutter_id + "/state", state)

    def sendMQTT(self, topic, msg):
        self.LogInfo("MQTT publish: " + topic + " = " + msg)
        self.t.publish(topic, msg, retain=True)

    def _remove_old_discovery(self):
        """Clear old-format discovery entries to prevent duplicate entities."""
        for shutter, shutter_id in sorted(self.config.ShuttersByName.items(), key=lambda kv: kv[1]):
            old_topic = "homeassistant/cover/" + shutter_id + "/config"
            self.t.publish(old_topic, "", retain=True)

    def sendStartupInfo(self):
        """Publish Home Assistant MQTT discovery for bridge and all shutters."""
        self._remove_old_discovery()

        bridge_msg = BridgeDiscoveryMsg(self.bridge_id, self._web_url)
        self.sendMQTT(bridge_msg.topic, bridge_msg.json())

        for shutter, shutter_id in sorted(self.config.ShuttersByName.items(), key=lambda kv: kv[1]):
            msg = DiscoveryMsg(shutter, shutter_id, self.bridge_id, self._web_url)
            self.sendMQTT(msg.topic, msg.json())

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.LogInfo("Connected to MQTT (rc=" + str(rc) + ")")
            self.connected_flag = True

            # Mark bridge as online
            self.sendMQTT(AVAILABILITY_TOPIC, "online")

            # Subscribe to command and position topics for each shutter
            for shutter, shutter_id in sorted(self.config.ShuttersByName.items(), key=lambda kv: kv[1]):
                self.LogInfo("Subscribing: " + shutter)
                self.t.subscribe(TOPIC_PREFIX + "/" + shutter_id + "/command")
                self.t.subscribe(TOPIC_PREFIX + "/" + shutter_id + "/set_position")

            # Publish discovery if enabled
            if self.config.EnableDiscovery == True:
                self.LogInfo("Publishing Home Assistant MQTT discovery")
                self.sendStartupInfo()

            # Publish current positions for all shutters
            for shutter, shutter_id in sorted(self.config.ShuttersByName.items(), key=lambda kv: kv[1]):
                position = self.shutter.getPosition(shutter_id)
                if position is not None:
                    self.set_state(shutter_id, position)

        else:
            self.LogError("MQTT connection failed (rc=" + str(rc) + ")")
            self.connected_flag = False

    def on_disconnect(self, client, userdata, rc=0):
        self.connected_flag = False
        if rc != 0:
            self.LogInfo("Disconnected from MQTT (rc=" + str(rc) + ")")

    def set_state(self, shutter_id, level):
        """Callback invoked when a shutter's position changes."""
        self.LogInfo("Shutter " + shutter_id + " position changed to " + str(level))
        self.sendMQTT(TOPIC_PREFIX + "/" + shutter_id + "/position", str(level))

        if level >= 100:
            self._publish_state(shutter_id, "open")
        elif level <= 0:
            self._publish_state(shutter_id, "closed")
        else:
            self._publish_state(shutter_id, "stopped")

    def set_movement_state(self, shutter_id, state):
        """Callback invoked when a shutter starts moving or stops — fired
        identically for software (TX) and physical-remote-triggered
        movement. Complements set_state's position-derived open/closed/
        stopped signal with the transient opening/closing state during
        travel."""
        self.LogInfo("Shutter " + shutter_id + " movement state: " + state)
        self._publish_state(shutter_id, state)

    def run(self):
        self.connected_flag = False
        self.LogInfo("Starting MQTT thread")

        # Create client (compatible with paho-mqtt 1.x and 2.x)
        try:
            # paho-mqtt >= 2.0 requires CallbackAPIVersion
            self.t = paho.Client(paho.CallbackAPIVersion.VERSION1, client_id=self.config.MQTT_ClientID)
        except (AttributeError, TypeError):
            # paho-mqtt < 2.0
            self.t = paho.Client(client_id=self.config.MQTT_ClientID)

        # Authentication
        if self.config.MQTT_Password.strip():
            self.t.username_pw_set(username=self.config.MQTT_User, password=self.config.MQTT_Password)

        # Last Will and Testament — broker publishes "offline" on unexpected disconnect
        self.t.will_set(AVAILABILITY_TOPIC, "offline", retain=True)

        self.t.on_connect = self.on_connect
        self.t.on_message = self.receiveMessageFromMQTT
        self.t.on_disconnect = self.on_disconnect
        self.shutter.registerCallBack(self.set_state)
        self.shutter.registerMovementCallBack(self.set_movement_state)

        # Initial connection with retry
        error = 0
        while not self.shutdown_flag.is_set():
            try:
                self.LogInfo("Connecting to MQTT broker at " + self.config.MQTT_Server + ":" + str(self.config.MQTT_Port))
                self.t.connect(self.config.MQTT_Server, self.config.MQTT_Port)
                break
            except Exception as e:
                error += 1
                self.LogInfo("MQTT connect attempt " + str(error) + " failed: " + str(e))
                time.sleep(10)

        # Start the paho-mqtt background network thread.
        # This processes incoming messages and sends outgoing publishes
        # immediately from any thread — critical so that state updates
        # published from waitAndSetFinalPosition threads are delivered
        # without waiting for a manual loop() call.
        self.t.loop_start()

        # Keep this thread alive until shutdown is requested;
        # reconnection is handled automatically by paho's loop thread.
        while not self.shutdown_flag.is_set():
            try:
                if not self.connected_flag:
                    self.LogInfo("Reconnecting to MQTT broker")
                    self.t.reconnect()
                time.sleep(5)
            except Exception as e:
                self.LogInfo("MQTT reconnect failed: " + str(e))
                time.sleep(10)

        # Clean shutdown
        try:
            self.t.publish(AVAILABILITY_TOPIC, "offline", retain=True)
            time.sleep(1)
            self.t.loop_stop()
            self.t.disconnect()
        except Exception:
            pass
        self.LogError("MQTT thread stopped")

