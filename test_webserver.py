# -*- coding: utf-8 -*-
"""webserver.py unit tests for the M2 Physical Remotes endpoints.

Needs Flask (and receiver.py's import, which only needs config.py — no
pigpio/lgpio required just to import webserver.py), so this whole file
skips cleanly if Flask isn't installed rather than failing collection.

    python3 -m unittest discover
"""

import json
import logging
import unittest

logging.getLogger("test_webserver").addHandler(logging.NullHandler())
LOG = logging.getLogger("test_webserver")
LOG.setLevel(logging.CRITICAL)

try:
    from webserver import FlaskAppWrapper
    _HAVE_WEBSERVER = True
except Exception:
    _HAVE_WEBSERVER = False


def result_of(response):
    """processCommand() returns Response(json.dumps(...)) without setting
    content_type=application/json, so Flask's own response.get_json()
    returns None — parse the raw body instead (true for every endpoint,
    not just the ones under test here)."""
    return json.loads(response.data)


class FakeConfig(object):
    def __init__(self, password=""):
        self.Password = password
        self.Latitude = 0
        self.Longitude = 0
        self.Shutters = {
            "0x02aaaa": {"name": "Shutter A", "durationDown": 20, "durationUp": 20, "intermediatePosition": None},
            "0x02bbbb": {"name": "Shutter B", "durationDown": 20, "durationUp": 20, "intermediatePosition": None},
        }
        self.PhysicalRemotes = {}
        self.written = []   # [(entry, value, section), ...]
        self.removed = []   # [(entry, section), ...]

    def WriteValue(self, entry, value, section=None):
        self.written.append((entry, value, section))
        return True

    def RemoveValue(self, entry, section=None):
        self.removed.append((entry, section))
        return True


class FakeShutter(object):
    def __init__(self, movement_states=None):
        self._movement_states = movement_states or {}

    def getPosition(self, shutterId):
        return 50

    def getMovementState(self, shutterId):
        return self._movement_states.get(shutterId)


class FakeSchedule(object):
    def getScheduleAsDict(self):
        return {}


class FakeReceiver(object):
    def __init__(self, unknown_remotes=()):
        self._unknown_remotes = list(unknown_remotes)


def make_client(config=None, receiver=None, shutter=None):
    config = config or FakeConfig()
    wrapper = FlaskAppWrapper(name="test", static_url_path="", log=LOG,
                              shutter=shutter or FakeShutter(), schedule=FakeSchedule(),
                              config=config, receiver=receiver)
    return wrapper.app.test_client(), config


@unittest.skipUnless(_HAVE_WEBSERVER, "Flask is required to test webserver.py")
class GetStatusTests(unittest.TestCase):
    """getStatus exposes the same movementState signal MQTT gets pushed, so
    the HA custom component's REST polling can show opening/closing for any
    trigger source (physical remote, web UI, or Home Assistant itself)."""

    def test_includes_movement_state_per_shutter(self):
        shutter = FakeShutter(movement_states={"0x02aaaa": "opening"})
        client, _ = make_client(shutter=shutter)
        result = result_of(client.get("/cmd/getStatus"))
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["shutters"]["0x02aaaa"]["movementState"], "opening")

    def test_movement_state_is_none_when_never_moved(self):
        client, _ = make_client(shutter=FakeShutter())
        result = result_of(client.get("/cmd/getStatus"))
        self.assertIsNone(result["shutters"]["0x02aaaa"]["movementState"])


@unittest.skipUnless(_HAVE_WEBSERVER, "Flask is required to test webserver.py")
class GetUnheardRemotesTests(unittest.TestCase):

    def test_empty_when_no_receiver(self):
        client, _ = make_client(receiver=None)
        result = result_of(client.get("/cmd/getUnheardRemotes"))
        self.assertEqual(result, {"status": "OK", "remotes": []})

    def test_lists_unknown_remotes(self):
        receiver = FakeReceiver([("0xabcdef", 2, 100)])
        client, _ = make_client(receiver=receiver)
        result = result_of(client.get("/cmd/getUnheardRemotes"))
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(result["remotes"]), 1)
        self.assertEqual(result["remotes"][0]["address"], "0xabcdef")
        self.assertEqual(result["remotes"][0]["buttonName"], "UP")

    def test_dedupes_by_address_keeping_most_recent(self):
        receiver = FakeReceiver([("0xabcdef", 2, 100), ("0xabcdef", 4, 101)])
        client, _ = make_client(receiver=receiver)
        result = result_of(client.get("/cmd/getUnheardRemotes"))
        self.assertEqual(len(result["remotes"]), 1)
        self.assertEqual(result["remotes"][0]["rollingCode"], 101)

    def test_ungated_even_with_password_set(self):
        client, _ = make_client(config=FakeConfig(password="secret"), receiver=FakeReceiver())
        result = result_of(client.get("/cmd/getUnheardRemotes"))
        self.assertEqual(result["status"], "OK")


@unittest.skipUnless(_HAVE_WEBSERVER, "Flask is required to test webserver.py")
class AssignRemoteTests(unittest.TestCase):

    def test_assigns_and_updates_config(self):
        client, config = make_client()
        result = result_of(client.post("/cmd/assignRemote",
                           data={"address": "0xABCDEF", "shutterIds[]": ["0x02aaaa", "0x02bbbb"]}))
        self.assertEqual(result["status"], "OK")
        # normalized to lowercase before writing
        self.assertEqual(config.written, [("0xabcdef", "0x02aaaa,0x02bbbb", "PhysicalRemotes")])
        self.assertEqual(config.PhysicalRemotes["0xabcdef"], ["0x02aaaa", "0x02bbbb"])

    def test_rejects_unknown_shutter(self):
        client, config = make_client()
        result = result_of(client.post("/cmd/assignRemote",
                           data={"address": "0xabcdef", "shutterIds[]": ["0xnotreal"]}))
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(config.written, [])

    def test_rejects_empty_selection(self):
        client, config = make_client()
        result = result_of(client.post("/cmd/assignRemote", data={"address": "0xabcdef"}))
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(config.written, [])

    def test_requires_password_when_configured(self):
        client, config = make_client(config=FakeConfig(password="secret"))
        result = result_of(client.post("/cmd/assignRemote",
                           data={"address": "0xabcdef", "shutterIds[]": ["0x02aaaa"]}))
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(config.written, [])

    def test_succeeds_with_correct_password(self):
        client, config = make_client(config=FakeConfig(password="secret"))
        result = result_of(client.post("/cmd/assignRemote",
                           data={"address": "0xabcdef", "shutterIds[]": ["0x02aaaa"]},
                           headers={"Password": "secret"}))
        self.assertEqual(result["status"], "OK")


@unittest.skipUnless(_HAVE_WEBSERVER, "Flask is required to test webserver.py")
class UnassignRemoteTests(unittest.TestCase):

    def test_unassigns_existing_mapping(self):
        config = FakeConfig()
        config.PhysicalRemotes["0xabcdef"] = ["0x02aaaa"]
        client, _ = make_client(config=config)
        result = result_of(client.post("/cmd/unassignRemote", data={"address": "0xabcdef"}))
        self.assertEqual(result["status"], "OK")
        self.assertNotIn("0xabcdef", config.PhysicalRemotes)
        self.assertEqual(config.removed, [("0xabcdef", "PhysicalRemotes")])

    def test_second_unassign_reports_not_assigned(self):
        config = FakeConfig()
        config.PhysicalRemotes["0xabcdef"] = ["0x02aaaa"]
        client, _ = make_client(config=config)
        client.post("/cmd/unassignRemote", data={"address": "0xabcdef"})
        result = result_of(client.post("/cmd/unassignRemote", data={"address": "0xabcdef"}))
        self.assertEqual(result["status"], "ERROR")

    def test_requires_password_when_configured(self):
        config = FakeConfig(password="secret")
        config.PhysicalRemotes["0xabcdef"] = ["0x02aaaa"]
        client, _ = make_client(config=config)
        result = result_of(client.post("/cmd/unassignRemote", data={"address": "0xabcdef"}))
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("0xabcdef", config.PhysicalRemotes)


if __name__ == "__main__":
    unittest.main()
