#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Standalone Somfy RTS sniffer — proof of concept (design doc §7).

Validates hardware, frequency, range and the RTS decoder with zero coupling to
Pi-Somfy's code:

  CC1101 @ 433.42 MHz OOK, async serial out on GDO0
    -> GPIO edge timestamps (pigpio callbacks on Pi 1-4, lgpio alerts on Pi 5)
    -> RTSDecoder (sync detect -> manchester -> de-XOR -> checksum)
    -> press log:  "0x14A2C7  UP  code=1337  repeats=4"

The frame/waveform generation is copied (not imported) from
Shutter.sendCommand in operateShutters.py, which is the authoritative
reference for the frame layout — it doubles as the built-in loopback
transmitter so the RX chain can be tested without a physical remote.

The decoder is a pure function of a (level, timestamp_us) edge stream and has
no GPIO dependencies: run the unit tests anywhere with
    python3 -m unittest discover addons/rts_sniffer_poc
"""

import argparse
import collections
import json
import logging
import os
import signal
import sys
import threading
import time

# GPIO / MQTT libraries are only needed on the Pi. Import lazily so the
# decoder stays unit-testable on any dev machine (design doc §9).
try:
    import pigpio
except ImportError:
    pigpio = None
try:
    import lgpio
except ImportError:
    lgpio = None
try:
    import paho.mqtt.client as paho_mqtt
except ImportError:
    paho_mqtt = None


# ── Pi model detection (copied from operateShutters.py — POC is standalone) ──
# Pi 5 uses the RP1 southbridge chip which is incompatible with pigpio.
IS_PI5 = False
LGPIO_CHIP = 4   # gpiochip number for lgpio (Pi 5): 4 on older kernels, 0 on newer
if sys.platform.startswith("linux"):
    try:
        with open('/proc/device-tree/model', 'r') as f:
            _model = f.read()
        if 'Pi 5' in _model:
            IS_PI5 = True
    except (FileNotFoundError, PermissionError):
        pass
    if not IS_PI5 and os.path.exists('/dev/gpiochip4'):
        IS_PI5 = True
    if not IS_PI5:
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Revision') and any(rev in line for rev in ['c04170', 'd04170', 'c04171', 'd04171']):
                        IS_PI5 = True
                        break
        except (FileNotFoundError, PermissionError):
            pass


# ── RTS protocol constants (must match Shutter.sendCommand exactly, §3) ─────
WAKEUP_HIGH_US = 9415
WAKEUP_LOW_US = 89565
HW_SYNC_HALF_US = 2560     # one half of a hardware-sync pair
SW_SYNC_HIGH_US = 4550
HALF_SYMBOL_US = 640       # manchester half-symbol
INTER_FRAME_GAP_US = 30415
PAYLOAD_BITS = 56

BUTTON_STOP = 0x1
BUTTON_UP = 0x2
BUTTON_DOWN = 0x4
BUTTON_PROG = 0x8
BUTTON_NAMES = {BUTTON_STOP: "MY/STOP", BUTTON_UP: "UP",
                BUTTON_DOWN: "DOWN", BUTTON_PROG: "PROG"}


def button_name(button):
    return BUTTON_NAMES.get(button, "0x%X" % button)


def build_frame(address, button, rolling_code):
    """Return the 7 obfuscated on-air bytes for one press.

    Copied from Shutter.sendCommand (operateShutters.py) — checksum over all
    14 nibbles, then the chained XOR obfuscation.
    """
    frame = bytearray(7)
    frame[0] = 0xA7                          # "encryption key"
    frame[1] = (button & 0xF) << 4           # button; low nibble becomes checksum
    frame[2] = (rolling_code >> 8) & 0xFF    # rolling code, big endian
    frame[3] = rolling_code & 0xFF
    frame[4] = (address >> 16) & 0xFF        # remote address, 24 bit
    frame[5] = (address >> 8) & 0xFF
    frame[6] = address & 0xFF

    checksum = 0
    for octet in frame:
        checksum = checksum ^ octet ^ (octet >> 4)
    frame[1] |= checksum & 0x0F

    for i in range(1, 7):                    # obfuscation: running XOR chain
        frame[i] ^= frame[i - 1]
    return frame


def frame_to_pulses(frame, repetitions=1):
    """On-air pulse list [(level, duration_us)] for one press.

    Same pulse table as Shutter.sendCommand: wake-up, then `repetitions`
    frames (2 hardware-sync pairs on the first, 7 on repeats). Consecutive
    same-level entries occur (e.g. software-sync low followed by a bit
    starting low) — they merge on air; pulses_to_edges() models that.
    """
    pulses = [(1, WAKEUP_HIGH_US), (0, WAKEUP_LOW_US)]
    for rep in range(repetitions):
        for _ in range(2 if rep == 0 else 7):        # hardware synchronization
            pulses.append((1, HW_SYNC_HALF_US))
            pulses.append((0, HW_SYNC_HALF_US))
        pulses.append((1, SW_SYNC_HIGH_US))          # software synchronization
        pulses.append((0, HALF_SYMBOL_US))
        for i in range(PAYLOAD_BITS):                # manchester payload
            if (frame[i // 8] >> (7 - (i % 8))) & 1:
                pulses.append((0, HALF_SYMBOL_US))
                pulses.append((1, HALF_SYMBOL_US))
            else:
                pulses.append((1, HALF_SYMBOL_US))
                pulses.append((0, HALF_SYMBOL_US))
        pulses.append((0, INTER_FRAME_GAP_US))       # inter-frame gap
    return pulses


def pulses_to_edges(pulses, start_us=0):
    """Convert a pulse list to the (level, timestamp_us) edge events a GPIO
    edge callback would deliver: consecutive same-level pulses merge into one,
    an event fires at every level change. The line is assumed idle-low."""
    edges = []
    t = start_us
    prev_level = 0
    for level, duration in pulses:
        if level != prev_level:
            edges.append((level, t))
            prev_level = level
        t += duration
    if prev_level != 0:
        edges.append((0, t))
    return edges


RTSFrame = collections.namedtuple("RTSFrame", "address button rolling_code key")


class RTSDecoder(object):
    """RTS frame decoder: a pure state machine fed (level, timestamp_us) edge
    events (design doc §5.1).

    1. Hunt for >=2 hardware-sync pairs (2560 us +/-30 %).
    2. Software sync high (4550 us) flips to payload collection.
    3. Payload durations classify as one half-symbol (640 us +/-35 %) or two;
       the first out-of-tolerance duration aborts straight back to sync hunt,
       re-examining the offending duration as a candidate new sync.
    4. De-obfuscate, verify checksum, emit {address, button, rollingCode}.

    Payload model: after the software-sync high the stream is 113 half-symbol
    slots — index 0 is the 640 us sync tail (low), indices 2k+1 / 2k+2 are the
    two manchester halves of bit k. Within a bit the halves always differ, so
    bit k = NOT(level of half 2k+1) and the frame is complete once half 111
    is assigned (112 halves seen). That also means a 2-half-long run may never
    start on an odd index — enforcing this catches invalid manchester early.
    """

    SYNC_TOL = 0.30
    SYM_TOL = 0.35
    HW_SYNC_MIN = int(HW_SYNC_HALF_US * (1 - SYNC_TOL))       # 1792
    # The +/-30 % windows of 2560 and 4550 overlap (3185..3328); split at the
    # midpoint so every duration classifies unambiguously as one or the other.
    HW_SW_SPLIT = (HW_SYNC_HALF_US + SW_SYNC_HIGH_US) // 2    # 3555
    SW_SYNC_MAX = int(SW_SYNC_HIGH_US * (1 + SYNC_TOL))       # 5915
    SYM_MIN = int(HALF_SYMBOL_US * (1 - SYM_TOL))             # 416
    SYM_SPLIT = (HALF_SYMBOL_US + 2 * HALF_SYMBOL_US) // 2    # 960
    SYM_MAX = int(2 * HALF_SYMBOL_US * (1 + SYM_TOL))         # 1728
    MIN_SYNC_HALVES = 4        # >= 2 hardware-sync pairs

    def __init__(self, on_frame=None):
        self.on_frame = on_frame
        self.frames_decoded = 0
        self.checksum_failures = 0
        self.payload_aborts = 0
        self.edge_count = 0
        self._last_ts = None
        self._last_level = None
        self._sync_halves = 0
        self._halves = None    # None -> hunting; list -> collecting payload

    def reset(self):
        self._sync_halves = 0
        self._halves = None

    def on_edge(self, level, ts_us):
        """Feed one edge: the line changed to `level` at `ts_us` (monotonic)."""
        if level not in (0, 1):          # pigpio watchdog / lgpio timeout events
            return
        self.edge_count += 1
        if self._last_ts is None or level == self._last_level:
            # First edge ever, or a missed edge left us out of phase: resync.
            self._last_ts = ts_us
            self._last_level = level
            self.reset()
            return
        duration = ts_us - self._last_ts
        ended_level = self._last_level   # the level held since the previous edge
        self._last_ts = ts_us
        self._last_level = level
        if self._halves is None:
            self._hunt(ended_level, duration)
        else:
            self._collect(ended_level, duration)

    def _hunt(self, level, duration):
        if self.HW_SYNC_MIN <= duration < self.HW_SW_SPLIT:
            self._sync_halves += 1
        elif (level == 1 and self._sync_halves >= self.MIN_SYNC_HALVES
                and self.HW_SW_SPLIT <= duration <= self.SW_SYNC_MAX):
            self._halves = []            # software sync seen -> collect payload
            self._sync_halves = 0
        else:
            self._sync_halves = 0

    def _collect(self, level, duration):
        if duration < self.SYM_MIN or duration > self.SYM_MAX:
            n = None
        elif duration < self.SYM_SPLIT:
            n = 1
        else:
            n = 2
        if n is None or (n == 2 and len(self._halves) % 2 == 1):
            self.payload_aborts += 1
            self.reset()
            self._hunt(level, duration)  # offending duration may be a new sync
            return
        self._halves.extend((level,) * n)
        if len(self._halves) >= 2 * PAYLOAD_BITS:
            self._finish_frame()

    def _finish_frame(self):
        halves = self._halves
        self.reset()

        recv = bytearray(7)
        for i in range(PAYLOAD_BITS):
            bit = halves[2 * i + 1] ^ 1
            recv[i // 8] |= bit << (7 - (i % 8))

        plain = bytearray(recv)          # de-obfuscation: plain[i] = recv[i] ^ recv[i-1]
        for i in range(6, 0, -1):
            plain[i] = recv[i] ^ recv[i - 1]

        checksum = 0                     # XOR of all 14 nibbles must be 0
        for octet in plain:
            checksum ^= octet ^ (octet >> 4)
        if checksum & 0x0F:
            self.checksum_failures += 1
            return

        frame = RTSFrame(
            address=(plain[4] << 16) | (plain[5] << 8) | plain[6],
            button=(plain[1] >> 4) & 0xF,
            rolling_code=(plain[2] << 8) | plain[3],
            key=plain[0])
        self.frames_decoded += 1
        if self.on_frame is not None:
            self.on_frame(frame)


class PressTracker(object):
    """Collapse the frame repeats of a single press into one press event.

    (address, rollingCode) uniquely identifies one press (§3) and is
    remembered with a TTL; on_press fires on the first frame, on_press_end
    fires with the final repeat count once the press goes quiet.
    """

    def __init__(self, on_press=None, on_press_end=None,
                 ttl=3.0, quiet=0.8, clock=time.monotonic):
        self.on_press = on_press
        self.on_press_end = on_press_end
        self.presses = 0
        self._ttl = ttl
        self._quiet = quiet
        self._clock = clock
        self._lock = threading.Lock()
        self._current = None

    def on_frame(self, frame):
        now = self._clock()
        ended = None
        with self._lock:
            cur = self._current
            if (cur is not None
                    and cur["key"] == (frame.address, frame.rolling_code)
                    and now - cur["last"] <= self._ttl):
                cur["repeats"] += 1
                cur["last"] = now
                return
            ended = self._take_current()
            self._current = {"key": (frame.address, frame.rolling_code),
                             "frame": frame, "repeats": 1,
                             "first": now, "last": now}
            self.presses += 1
        self._emit_end(ended)
        if self.on_press is not None:
            self.on_press(frame)

    def poll(self):
        """Call periodically; flushes a press once it has gone quiet."""
        now = self._clock()
        with self._lock:
            if self._current is None or now - self._current["last"] < self._quiet:
                return
            ended = self._take_current()
        self._emit_end(ended)

    def _take_current(self):
        cur, self._current = self._current, None
        return cur

    def _emit_end(self, ended):
        if ended is not None and self.on_press_end is not None:
            self.on_press_end(ended["frame"], ended["repeats"])


# ── CC1101 configuration via bit-banged SPI (design doc §5.1, Appendix A) ───

CC1101_SRES = 0x30
CC1101_SRX = 0x34
CC1101_SIDLE = 0x36
CC1101_READ = 0x80
CC1101_STATUS = 0xC0            # burst bit selects the status-register space
CC1101_REG_PARTNUM = 0x30
CC1101_REG_VERSION = 0x31
CC1101_REG_RSSI = 0x34
CC1101_REG_MARCSTATE = 0x35
CC1101_MARCSTATE_RX = 0x0D

# Register map, 26 MHz crystal, 433.42 MHz ASK/OOK asynchronous serial data
# out on GDO0. FREQ is derived from the datasheet formula; the rest is a
# faithful port of SmartRC-CC1101-Driver-Lib's register set for ~100 kHz
# bandwidth (the library behind Elrindel/SomfyReceiver's confirmed-working
# example on this same physical module), with full LNA/DVGA gain instead of
# the reference's capped-gain AGCCTRL2 — capping gain reliably killed all
# receive activity on this specific hardware. Validated end-to-end on real
# hardware: loopback decodes at 100%, real remote presses decode correctly.
#
# MANCHESTER_EN and SYNC_MODE (in MDMCFG2) are set to match the reference
# but are, per the datasheet, packet-engine features tied to bit-clock
# recovery that asynchronous serial mode has none of — almost certainly
# don't-care bits here, matched only for completeness.
CC1101_RX_CONFIG = (
    (0x00, 0x2E, "IOCFG2   GDO2 high impedance (unused, not wired)"),
    (0x02, 0x0D, "IOCFG0   GDO0 = asynchronous serial RX data"),
    (0x06, 0x00, "PKTLEN   unused in infinite-length async mode"),
    (0x07, 0x04, "PKTCTRL1 no address check, no status append"),
    (0x08, 0x32, "PKTCTRL0 asynchronous serial mode, no CRC, infinite length"),
    (0x09, 0x00, "ADDR     unused (no address check)"),
    (0x0A, 0x00, "CHANNR   channel 0, no channel hopping"),
    (0x0B, 0x06, "FSCTRL1  IF = 26MHz*6/2^10 = 152 kHz"),
    (0x0D, 0x10, "FREQ2    FREQ=0x10AB85 = round(433.42MHz * 2^16 / 26MHz)"),
    (0x0E, 0xAB, "FREQ1    -> carrier 433.419995 MHz"),
    (0x0F, 0x85, "FREQ0"),
    (0x10, 0xC7, "MDMCFG4  RX BW 26MHz/(8*(4+0)*2^3) = 101.6 kHz; DRATE_E=7"),
    (0x11, 0x93, "MDMCFG3  DRATE_M=0x93, paired with DRATE_E=7 above"),
    (0x12, 0x3C, "MDMCFG2  DC-blocking filter on, ASK/OOK (MOD_FORMAT=011), "
                 "MANCHESTER_EN=1, SYNC_MODE=100 (likely don't-care in async "
                 "serial mode, see note above; matched for completeness)"),
    (0x13, 0x02, "MDMCFG1  no FEC, minimal preamble (irrelevant in async mode)"),
    (0x14, 0xF8, "MDMCFG0  channel spacing (irrelevant, no channel hopping)"),
    (0x15, 0x47, "DEVIATN  frequency deviation (FSK-only, irrelevant for OOK)"),
    (0x18, 0x18, "MCSM0    auto-calibrate synthesizer on IDLE->RX"),
    (0x19, 0x16, "FOCCFG   frequency offset compensation"),
    (0x1A, 0x1C, "BSCFG    bit synchronization config"),
    (0x1B, 0x03, "AGCCTRL2 full LNA/DVGA gain, 33 dB magnitude target — "
                 "capping DVGA gain reliably killed all receive activity on "
                 "this hardware"),
    (0x1C, 0x00, "AGCCTRL1 no relative carrier-sense thresholds"),
    (0x1D, 0x91, "AGCCTRL0 OOK decision boundary 8 dB above averaged noise "
                 "floor, 16-sample window"),
    (0x21, 0x56, "FREND1   RX front end"),
    (0x22, 0x11, "FREND0   OOK PA table index 1 (TX side unused in this POC)"),
    (0x23, 0xE9, "FSCAL3   frequency synthesizer calibration"),
    (0x24, 0x2A, "FSCAL2   same"),
    (0x25, 0x00, "FSCAL1   same"),
    (0x26, 0x1F, "FSCAL0   same"),
    (0x29, 0x59, "FSTEST"),
    (0x2C, 0x81, "TEST2    RX BW >= 325 kHz value (datasheet threshold, not "
                 "linear in bandwidth — still correct for our narrower filter)"),
    (0x2D, 0x35, "TEST1    same threshold basis as TEST2"),
    (0x2E, 0x09, "TEST0    VCO selection calibration disabled"),
)


class PigpioBitBangSpi(object):
    """Bit-banged SPI on Pi 1-4 via pigpiod's built-in bb_spi_* (any GPIOs)."""

    def __init__(self, pi, sck, mosi, miso, csn, baud=50000):
        self._pi = pi
        self._csn = csn
        pi.bb_spi_open(csn, miso, mosi, sck, baud, 0)   # SPI mode 0, MSB first

    def xfer(self, data):
        count, rx = self._pi.bb_spi_xfer(self._csn, data)
        if count < 0:
            raise RuntimeError("bb_spi_xfer failed with %d" % count)
        return list(rx)

    def close(self):
        try:
            self._pi.bb_spi_close(self._csn)
        except Exception:
            pass


class LgpioBitBangSpi(object):
    """Bit-banged SPI mode 0 with plain lgpio reads/writes (Pi 5).

    Speed is irrelevant — the CC1101 is configured once at startup — so a
    software half-clock of ~10 us (~50 kHz) is plenty.
    """

    HALF_CLOCK_S = 0.00001

    def __init__(self, handle, sck, mosi, miso, csn):
        self._h = handle
        self._sck, self._mosi, self._miso, self._csn = sck, mosi, miso, csn
        lgpio.gpio_claim_output(handle, sck, 0)
        lgpio.gpio_claim_output(handle, mosi, 0)
        lgpio.gpio_claim_output(handle, csn, 1)
        lgpio.gpio_claim_input(handle, miso)

    def xfer(self, data):
        h = self._h
        lgpio.gpio_write(h, self._csn, 0)
        # The CC1101 drives SO low once its crystal is stable; wait briefly.
        deadline = time.monotonic() + 0.01
        while lgpio.gpio_read(h, self._miso) and time.monotonic() < deadline:
            time.sleep(0.0001)
        rx = []
        for byte in data:
            value = 0
            for bit in range(7, -1, -1):
                lgpio.gpio_write(h, self._mosi, (byte >> bit) & 1)
                time.sleep(self.HALF_CLOCK_S)
                lgpio.gpio_write(h, self._sck, 1)
                value = (value << 1) | lgpio.gpio_read(h, self._miso)
                time.sleep(self.HALF_CLOCK_S)
                lgpio.gpio_write(h, self._sck, 0)
            rx.append(value)
        lgpio.gpio_write(h, self._csn, 1)
        return rx

    def close(self):
        for gpio in (self._sck, self._mosi, self._miso, self._csn):
            try:
                lgpio.gpio_free(self._h, gpio)
            except Exception:
                pass


class CC1101(object):
    """One-time CC1101 setup: 433.42 MHz OOK receive, demodulated data on GDO0.

    Init must prove the radio is really there and configured (§5.1): VERSION
    is read first, every register write is read back, and the receiver state
    is verified — any mismatch aborts startup loudly, because a mis-wired SPI
    otherwise degrades silently into a deaf receiver.
    """

    def __init__(self, spi, log):
        self._spi = spi
        self._log = log

    def _strobe(self, cmd):
        status = self._spi.xfer([cmd])[0]
        if status & 0x80:    # CHIP_RDYn must be low on every returned status byte
            raise RuntimeError(
                "CC1101 status byte 0x%02X reports chip not ready after strobe 0x%02X"
                % (status, cmd))
        return status

    def _write_reg(self, addr, value):
        self._spi.xfer([addr, value])

    def _read_reg(self, addr):
        return self._spi.xfer([addr | CC1101_READ, 0x00])[1]

    def _read_status_reg(self, addr):
        return self._spi.xfer([addr | CC1101_STATUS, 0x00])[1]

    def configure(self):
        self._spi.xfer([CC1101_SRES])
        time.sleep(0.01)

        partnum = self._read_status_reg(CC1101_REG_PARTNUM)
        version = self._read_status_reg(CC1101_REG_VERSION)
        if version in (0x00, 0xFF):
            raise RuntimeError(
                "CC1101 not responding (PARTNUM=0x%02X VERSION=0x%02X) — MISO stuck; "
                "check wiring/power. Match module pins by silkscreen label "
                "(MOSI may be printed SI, MISO SO)." % (partnum, version))
        self._log.info("CC1101 detected: PARTNUM=0x%02X VERSION=0x%02X "
                       "(genuine chips report 0x00/0x14; clones vary)",
                       partnum, version)

        for addr, value, note in CC1101_RX_CONFIG:
            self._write_reg(addr, value)
        mismatches = []
        for addr, value, note in CC1101_RX_CONFIG:
            readback = self._read_reg(addr)
            if readback != value:
                mismatches.append("reg 0x%02X (%s): wrote 0x%02X read 0x%02X"
                                  % (addr, note.split()[0], value, readback))
        if mismatches:
            raise RuntimeError("CC1101 register read-back failed — mis-wired SPI? "
                               + "; ".join(mismatches))

        self._strobe(CC1101_SIDLE)
        time.sleep(0.001)
        self._strobe(CC1101_SRX)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if self._read_status_reg(CC1101_REG_MARCSTATE) & 0x1F == CC1101_MARCSTATE_RX:
                self._log.info("CC1101 configured: 433.42 MHz OOK, async serial data on GDO0")
                return
            time.sleep(0.01)
        raise RuntimeError("CC1101 never entered RX (MARCSTATE=0x%02X)"
                           % self._read_status_reg(CC1101_REG_MARCSTATE))

    def rssi_dbm(self):
        raw = self._read_status_reg(CC1101_REG_RSSI)
        return (raw - 256 if raw >= 128 else raw) / 2.0 - 74

    def is_in_rx(self):
        return self._read_status_reg(CC1101_REG_MARCSTATE) & 0x1F == CC1101_MARCSTATE_RX


# ── Edge sources: normalise both GPIO backends to (level, timestamp_us) ─────

class PigpioEdgeSource(object):
    """pigpio edge callbacks (Pi 1-4): pigpiod timestamps every edge daemon-side
    in us ticks, so Python scheduling jitter does not affect decoding."""

    def __init__(self, pi, gpio, on_edge, glitch_us=150):
        self._pi = pi
        self._gpio = gpio
        self._on_edge = on_edge
        self._prev_tick = None
        self._ts = 0
        pi.set_mode(gpio, pigpio.INPUT)
        pi.set_glitch_filter(gpio, glitch_us)   # drop sub-150 us noise in the daemon
        self._cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._handle)

    def _handle(self, _gpio, level, tick):
        if self._prev_tick is not None:
            self._ts += pigpio.tickDiff(self._prev_tick, tick)  # 32-bit wrap safe
        self._prev_tick = tick
        try:
            self._on_edge(level, self._ts)
        except Exception:
            logging.getLogger("sniffer").exception("decoder error")

    def stop(self):
        self._cb.cancel()
        self._pi.set_glitch_filter(self._gpio, 0)


class LgpioEdgeSource(object):
    """lgpio alerts (Pi 5): kernel timestamps in ns, debounce as glitch filter."""

    def __init__(self, handle, gpio, on_edge, glitch_us=150):
        self._h = handle
        self._gpio = gpio
        self._on_edge = on_edge
        lgpio.gpio_claim_alert(handle, gpio, lgpio.BOTH_EDGES)
        lgpio.gpio_set_debounce_micros(handle, gpio, glitch_us)
        self._cb = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES, self._handle)

    def _handle(self, _chip, _gpio, level, timestamp_ns):
        try:
            self._on_edge(level, timestamp_ns // 1000)   # level 2 (watchdog) is ignored downstream
        except Exception:
            logging.getLogger("sniffer").exception("decoder error")

    def stop(self):
        self._cb.cancel()
        try:
            lgpio.gpio_free(self._h, self._gpio)
        except Exception:
            pass


# ── Loopback test transmitter (waveform copied from Shutter.sendCommand) ────

def send_pulses_pigpio(pi, tx_gpio, pulses):
    pi.wave_add_new()
    pi.set_mode(tx_gpio, pigpio.OUTPUT)
    wf = []
    for level, duration in pulses:
        if level:
            wf.append(pigpio.pulse(1 << tx_gpio, 0, duration))
        else:
            wf.append(pigpio.pulse(0, 1 << tx_gpio, duration))
    pi.wave_add_generic(wf)
    wid = pi.wave_create()
    pi.wave_send_once(wid)
    while pi.wave_tx_busy():
        time.sleep(0.005)
    pi.wave_delete(wid)


def send_pulses_lgpio(handle, tx_gpio, pulses):
    lgpio.gpio_claim_output(handle, tx_gpio)
    wave = [lgpio.pulse(level, 1, duration) for level, duration in pulses]
    lgpio.tx_wave(handle, tx_gpio, wave)
    while lgpio.tx_busy(handle, tx_gpio, lgpio.TX_WAVE):
        time.sleep(0.001)
    lgpio.gpio_free(handle, tx_gpio)


# ── Sniffer application ──────────────────────────────────────────────────────

class Sniffer(object):
    STATUS_INTERVAL_S = 60
    TEST_TX_REPETITIONS = 2
    TEST_TX_BUTTONS = (BUTTON_UP, BUTTON_STOP, BUTTON_DOWN)

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log
        self.shutdown_flag = threading.Event()
        self._pi = None
        self._lgpio_handle = None
        self._spi = None
        self._cc1101 = None
        self._edge_source = None
        self._mqtt = None
        self._tracker = PressTracker(on_press=self._on_press,
                                     on_press_end=self._on_press_end)
        self._decoder = RTSDecoder(on_frame=self._tracker.on_frame)
        self._test_code = 0
        self._loopback_expected = None
        self._loopback_sent = 0
        self._loopback_ok = 0

    # -- setup ---------------------------------------------------------------
    def start(self):
        opts = self.opts
        if IS_PI5:
            if lgpio is None:
                raise RuntimeError("lgpio module not available on this Pi 5")
            global LGPIO_CHIP
            last_error = None
            for chip in (4, 0):
                try:
                    self._lgpio_handle = lgpio.gpiochip_open(chip)
                    LGPIO_CHIP = chip
                    break
                except Exception as e:
                    last_error = e
            if self._lgpio_handle is None:
                raise RuntimeError("lgpio: no usable gpiochip found: %s" % last_error)
            self.log.info("Pi 5: lgpio on gpiochip%d", LGPIO_CHIP)
        else:
            if pigpio is None:
                raise RuntimeError("pigpio module not available")
            self._pi = pigpio.pi()
            if not self._pi.connected:
                raise RuntimeError("cannot connect to pigpiod — is it running?")
            self.log.info("Pi 1-4: connected to pigpiod")

        if IS_PI5:
            self._spi = LgpioBitBangSpi(self._lgpio_handle, opts.spi_sck,
                                        opts.spi_mosi, opts.spi_miso, opts.spi_csn)
        else:
            self._spi = PigpioBitBangSpi(self._pi, opts.spi_sck,
                                         opts.spi_mosi, opts.spi_miso, opts.spi_csn)
        self._cc1101 = CC1101(self._spi, self.log)
        self._cc1101.configure()

        if IS_PI5:
            self._edge_source = LgpioEdgeSource(self._lgpio_handle, opts.rx_gpio,
                                                self._decoder.on_edge)
        else:
            self._edge_source = PigpioEdgeSource(self._pi, opts.rx_gpio,
                                                 self._decoder.on_edge)
        self.log.info("Listening on GPIO %d", opts.rx_gpio)

        if opts.mqtt_host:
            self._start_mqtt()
        if opts.test_tx_interval:
            self.log.info("Loopback transmitter enabled: address 0x%06X on GPIO %d "
                          "every %d s", opts.test_address, opts.tx_gpio,
                          opts.test_tx_interval)

    def _start_mqtt(self):
        if paho_mqtt is None:
            self.log.warning("mqtt_host set but paho-mqtt is not installed — "
                             "MQTT publishing disabled")
            return
        try:
            client = paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            client = paho_mqtt.Client()
        if self.opts.mqtt_user:
            client.username_pw_set(self.opts.mqtt_user, self.opts.mqtt_password)
        client.connect_async(self.opts.mqtt_host, self.opts.mqtt_port)
        client.loop_start()
        self._mqtt = client
        self.log.info("MQTT: publishing presses to somfy_sniffer/event on %s:%d",
                      self.opts.mqtt_host, self.opts.mqtt_port)

    # -- press handling ------------------------------------------------------
    def _on_press(self, frame):
        if (self.opts.test_tx_interval
                and frame.address == self.opts.test_address):
            self._check_loopback(frame)
            return
        self.log.info("0x%06X  %s  code=%d", frame.address,
                      button_name(frame.button), frame.rolling_code)

    def _on_press_end(self, frame, repeats):
        if (self.opts.test_tx_interval
                and frame.address == self.opts.test_address):
            return
        self.log.info("0x%06X  %s  code=%d  repeats=%d", frame.address,
                      button_name(frame.button), frame.rolling_code, repeats)
        if self._mqtt is not None:
            payload = json.dumps({"address": "0x%06X" % frame.address,
                                  "button": button_name(frame.button),
                                  "rolling_code": frame.rolling_code,
                                  "repeats": repeats})
            self._mqtt.publish("somfy_sniffer/event", payload)

    def _check_loopback(self, frame):
        expected = self._loopback_expected
        if expected is not None and (frame.button, frame.rolling_code) == expected:
            self._loopback_ok += 1
            self._loopback_expected = None
            self.log.info("Loopback OK: %d/%d decoded (%.1f%%)",
                          self._loopback_ok, self._loopback_sent,
                          100.0 * self._loopback_ok / self._loopback_sent)
        else:
            self.log.warning("Loopback MISMATCH: heard %s code=%d, expected %s",
                             button_name(frame.button), frame.rolling_code, expected)

    # -- test transmitter ----------------------------------------------------
    def _send_test_frame(self):
        self._test_code += 1
        button = self.TEST_TX_BUTTONS[self._test_code % len(self.TEST_TX_BUTTONS)]
        frame = build_frame(self.opts.test_address, button, self._test_code)
        pulses = frame_to_pulses(frame, repetitions=self.TEST_TX_REPETITIONS)
        self._loopback_expected = (button, self._test_code)
        self._loopback_sent += 1
        self.log.info("Loopback TX #%d: 0x%06X %s code=%d", self._loopback_sent,
                      self.opts.test_address, button_name(button), self._test_code)
        if IS_PI5:
            send_pulses_lgpio(self._lgpio_handle, self.opts.tx_gpio, pulses)
        else:
            send_pulses_pigpio(self._pi, self.opts.tx_gpio, pulses)

    # -- main loop -----------------------------------------------------------
    def run(self):
        now = time.monotonic()
        next_status = now + self.STATUS_INTERVAL_S
        next_tx = now + 5 if self.opts.test_tx_interval else None
        while not self.shutdown_flag.is_set():
            time.sleep(0.2)
            self._tracker.poll()
            now = time.monotonic()
            if next_tx is not None and now >= next_tx:
                self._send_test_frame()
                next_tx = now + self.opts.test_tx_interval
            if now >= next_status:
                self._log_status()
                next_status = now + self.STATUS_INTERVAL_S

    def _log_status(self):
        d = self._decoder
        extra = ""
        if self._cc1101 is not None:
            try:
                extra = "  rssi=%.0f dBm  rx=%s" % (self._cc1101.rssi_dbm(),
                                                    self._cc1101.is_in_rx())
            except Exception as e:
                extra = "  (CC1101 status read failed: %s)" % e
        if self._loopback_sent:
            extra += "  loopback=%d/%d" % (self._loopback_ok, self._loopback_sent)
        self.log.info("Status: edges=%d presses=%d frames=%d checksum_fail=%d "
                      "payload_aborts=%d%s", d.edge_count, self._tracker.presses,
                      d.frames_decoded, d.checksum_failures, d.payload_aborts, extra)

    def stop(self):
        self.shutdown_flag.set()
        if self._edge_source is not None:
            self._edge_source.stop()
        if self._spi is not None:
            self._spi.close()
        if self._mqtt is not None:
            self._mqtt.loop_stop()
        if self._pi is not None:
            self._pi.stop()
        if self._lgpio_handle is not None:
            lgpio.gpiochip_close(self._lgpio_handle)


def parse_args(argv=None):
    def hex_int(value):
        return int(value, 0)

    p = argparse.ArgumentParser(description="Somfy RTS sniffer POC")
    p.add_argument("--rx-gpio", type=int, default=26,
                   help="GPIO wired to the receiver data pin (CC1101 GDO0)")
    p.add_argument("--spi-sck", type=int, default=21)
    p.add_argument("--spi-mosi", type=int, default=20)
    p.add_argument("--spi-miso", type=int, default=19)
    p.add_argument("--spi-csn", type=int, default=16)
    p.add_argument("--test-tx-interval", type=int, default=0, metavar="SECONDS",
                   help="transmit a loopback test frame every N seconds (0 = off)")
    p.add_argument("--tx-gpio", type=int, default=4,
                   help="GPIO of the existing 433.42 MHz transmitter")
    p.add_argument("--test-address", type=hex_int, default=0xDEC0DE,
                   help="dummy remote address used by the loopback transmitter")
    p.add_argument("--mqtt-host", default="")
    p.add_argument("--mqtt-port", type=int, default=1883)
    p.add_argument("--mqtt-user", default="")
    p.add_argument("--mqtt-password", default="")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    opts = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if opts.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        stream=sys.stdout)
    log = logging.getLogger("sniffer")

    if pigpio is None and lgpio is None:
        log.error("Neither pigpio nor lgpio is available — this must run on a "
                  "Raspberry Pi. (The decoder unit tests run anywhere: "
                  "python3 -m unittest discover addons/rts_sniffer_poc)")
        return 2

    sniffer = Sniffer(opts, log)

    def _shutdown(signum, _frame):
        log.info("Signal %d received, shutting down", signum)
        sniffer.shutdown_flag.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        sniffer.start()
        log.info("RTS sniffer running — press a Somfy remote button")
        sniffer.run()
    except Exception:
        log.exception("Fatal error")
        return 1
    finally:
        sniffer.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
