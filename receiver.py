#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Somfy RTS receiver — decodes physical remote presses and updates the
Shutter position model.

Configures a CC1101 receiver module over bit-banged SPI for 433.42 MHz OOK
reception, and decodes the RTS frame format (manchester-encoded, checksummed,
obfuscated via a running XOR chain). Runs as a Pi-Somfy service thread with a
TX-pause gate, so the receiver never tries to decode our own transmissions,
and a self-echo filter as a second line of defense. Known physical remotes
are mapped to shutters via [PhysicalRemotes] in the config file.
"""

import collections
import os
import sys
import threading
import time

from config import MyLog

# GPIO libraries are only needed on real hardware. Import lazily, and detect
# the Pi model independently below, so the decoder classes stay unit-testable
# on any dev machine. (operateShutters.py's own IS_PI5/LGPIO_CHIP aren't
# imported here on purpose: that module hard-imports ephem/pigpio/lgpio at
# load time, which would make `import receiver` fail on a plain dev machine.)
try:
    import pigpio
except ImportError:
    pigpio = None
try:
    import lgpio
except ImportError:
    lgpio = None


# ── Pi model detection (copied from operateShutters.py — see note above) ────
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


# ── RTS protocol constants (must match Shutter.sendCommand exactly) ─────────
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

# Bit-banged SPI GPIO defaults — used when RXSpiSCK/MOSI/MISO/CSN aren't set
# in [General].
DEFAULT_SPI_SCK = 21
DEFAULT_SPI_MOSI = 20
DEFAULT_SPI_MISO = 19
DEFAULT_SPI_CSN = 16


def button_name(button):
    return BUTTON_NAMES.get(button, "0x%X" % button)


def build_frame(address, button, rolling_code):
    """Return the 7 obfuscated on-air bytes for one press.

    Copied from Shutter.sendCommand (operateShutters.py) — checksum over all
    14 nibbles, then the chained XOR obfuscation. Used by test_receiver.py to
    build synthetic edge streams; the receiver itself only decodes.
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
    frames (2 hardware-sync pairs on the first, 7 on repeats).
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
    events.

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

    (address, rollingCode) uniquely identifies one press and is
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


# ── CC1101 configuration via bit-banged SPI ──────────────────────────────────

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
    (0x22, 0x11, "FREND0   OOK PA table index 1 (TX side unused here)"),
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

    Init must prove the radio is really there and configured: VERSION
    is read first, every register write is read back, and the receiver state
    is verified — any mismatch aborts startup loudly, because a mis-wired SPI
    otherwise degrades silently into a deaf receiver. `log` is a MyLog-style
    object (LogInfo/LogError), not a stdlib logger.
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
        self._log.LogInfo("CC1101 detected: PARTNUM=0x%02X VERSION=0x%02X "
                          "(genuine chips report 0x00/0x14; clones vary)" % (partnum, version))

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
                self._log.LogInfo("CC1101 configured: 433.42 MHz OOK, async serial data on GDO0")
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

    def __init__(self, pi, gpio, on_edge, log, glitch_us=150):
        self._pi = pi
        self._gpio = gpio
        self._on_edge = on_edge
        self._log = log
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
        except Exception as e:
            self._log.LogError("Receiver: decoder error: " + str(e))

    def stop(self):
        self._cb.cancel()
        self._pi.set_glitch_filter(self._gpio, 0)


class LgpioEdgeSource(object):
    """lgpio alerts (Pi 5): kernel timestamps in ns, debounce as glitch filter."""

    def __init__(self, handle, gpio, on_edge, log, glitch_us=150):
        self._h = handle
        self._gpio = gpio
        self._on_edge = on_edge
        self._log = log
        lgpio.gpio_claim_alert(handle, gpio, lgpio.BOTH_EDGES)
        lgpio.gpio_set_debounce_micros(handle, gpio, glitch_us)
        self._cb = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES, self._handle)

    def _handle(self, _chip, _gpio, level, timestamp_ns):
        try:
            self._on_edge(level, timestamp_ns // 1000)   # level 2 (watchdog) is ignored downstream
        except Exception as e:
            self._log.LogError("Receiver: decoder error: " + str(e))

    def stop(self):
        self._cb.cancel()
        try:
            lgpio.gpio_free(self._h, self._gpio)
        except Exception:
            pass


class Receiver(threading.Thread, MyLog):
    """Service thread: listens for physical Somfy RTS remote presses and
    updates Shutter's position model.

    Constructed and started the same way as Scheduler/MQTT (kwargs={'log',
    'shutter', 'config'}), gated on config.RXGPIO being set — no new CLI flag.
    All hardware bring-up happens in run(), never in __init__, so a
    mis-wired/missing CC1101 disables the receiver (logs an error and
    returns) instead of crashing the whole process.
    """

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        threading.Thread.__init__(self, group=group, target=target, name="Receiver")
        self.shutdown_flag = threading.Event()
        self.args = args
        self.kwargs = kwargs
        if kwargs["log"] is not None:
            self.log = kwargs["log"]
        if kwargs["shutter"] is not None:
            self.shutter = kwargs["shutter"]
        if kwargs["config"] is not None:
            self.config = kwargs["config"]
        # Optional: streams hardware bring-up status to the console/add-on
        # log (self.log alone is file-only), same as operateShutters.py's
        # own startGPIO() diagnostics. None-safe — LogConsole no-ops without it.
        self.console = kwargs.get("console")

        self._pi = None
        self._lgpio_handle = None
        self._spi = None
        self._cc1101 = None
        self._edge_source = None
        self._tx_gated = False
        # Presses from remotes not found in [PhysicalRemotes] — visible for
        # a future pairing UI — for now just logs them.
        self._unknown_remotes = collections.deque(maxlen=32)

        self._tracker = PressTracker(on_press=self._dispatch, on_press_end=self._on_press_end)
        self._decoder = RTSDecoder(on_frame=self._on_frame)

    # -- hardware bring-up -----------------------------------------------------
    def _start_hardware(self):
        rx_gpio = self.config.RXGPIO
        spi_sck = self.config.RXSpiSCK if self.config.RXSpiSCK is not None else DEFAULT_SPI_SCK
        spi_mosi = self.config.RXSpiMOSI if self.config.RXSpiMOSI is not None else DEFAULT_SPI_MOSI
        spi_miso = self.config.RXSpiMISO if self.config.RXSpiMISO is not None else DEFAULT_SPI_MISO
        spi_csn = self.config.RXSpiCSN if self.config.RXSpiCSN is not None else DEFAULT_SPI_CSN

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
            self.LogInfo("Receiver: Pi 5, lgpio on gpiochip%d" % LGPIO_CHIP)
            self.LogConsole("Receiver: Pi 5, lgpio on gpiochip%d" % LGPIO_CHIP)
            self._spi = LgpioBitBangSpi(self._lgpio_handle, spi_sck, spi_mosi, spi_miso, spi_csn)
        else:
            if pigpio is None:
                raise RuntimeError("pigpio module not available")
            self._pi = pigpio.pi()
            if not self._pi.connected:
                raise RuntimeError("cannot connect to pigpiod — is it running?")
            self.LogInfo("Receiver: connected to pigpiod")
            self.LogConsole("Receiver: connected to pigpiod")
            self._spi = PigpioBitBangSpi(self._pi, spi_sck, spi_mosi, spi_miso, spi_csn)

        self._cc1101 = CC1101(self._spi, self)
        self._cc1101.configure()
        self.LogConsole("Receiver: CC1101 configured")

        if IS_PI5:
            self._edge_source = LgpioEdgeSource(self._lgpio_handle, rx_gpio, self._on_edge, self)
        else:
            self._edge_source = PigpioEdgeSource(self._pi, rx_gpio, self._on_edge, self)
        self.LogInfo("Receiver: listening on GPIO %d" % rx_gpio)
        self.LogConsole("Receiver: listening on GPIO %d" % rx_gpio)

    def _stop_hardware(self):
        if self._edge_source is not None:
            self._edge_source.stop()
        if self._spi is not None:
            self._spi.close()
        if self._pi is not None:
            self._pi.stop()
        if self._lgpio_handle is not None:
            lgpio.gpiochip_close(self._lgpio_handle)

    # -- edge / frame / press pipeline -----------------------------------------
    # Sits between the edge source and the decoder: drop edges while our own
    # TX path is transmitting, and resync the decoder once TX ends — found
    # during earlier testing that a receiver left running during TX otherwise decodes
    # noise/reflections of our own frame.
    def _on_edge(self, level, ts_us):
        if self.shutter.transmitting.is_set():
            self._tx_gated = True
            return
        if self._tx_gated:
            self._tx_gated = False
            self._decoder.reset()
        self._decoder.on_edge(level, ts_us)

    # Sits between the decoder and the press tracker: a second, independent
    # defense against self-echo (catches cleanly-decoded frames outside the
    # TX-gated window, e.g. multipath) — neither defense subsumes the other.
    def _on_frame(self, frame):
        if ("0x%06x" % frame.address) in self.config.Shutters:
            return
        self._tracker.on_frame(frame)

    def _dispatch(self, frame):
        address = "0x%06x" % frame.address
        shutterIds = self.config.PhysicalRemotes.get(address)
        if not shutterIds:
            msg = ("Receiver: unknown remote " + address + " pressed " +
                  button_name(frame.button) + " (code=" + str(frame.rolling_code) + ")")
            self.LogInfo(msg)
            self.LogConsole(msg)
            self._unknown_remotes.append((address, frame.button, frame.rolling_code))
            return
        self.LogConsole("Receiver: " + address + " pressed " + button_name(frame.button) +
                        " -> " + ", ".join(shutterIds))
        for shutterId in shutterIds:
            if shutterId not in self.config.Shutters:
                self.LogWarn("Receiver: [PhysicalRemotes] " + address +
                            " maps to unknown shutterId " + shutterId)
                continue
            self.shutter.recordExternalCommand(shutterId, frame.button)

    def _on_press_end(self, frame, repeats):
        self.LogDebug("Receiver: 0x%06x %s repeats=%d" %
                      (frame.address, button_name(frame.button), repeats))

    # -- main loop ---------------------------------------------------------------
    def run(self):
        try:
            self._start_hardware()
        except Exception as e:
            self.LogError("Receiver: hardware init failed — receiver disabled: " + str(e))
            self.LogConsole("Receiver: hardware init failed — receiver disabled: " + str(e))
            self._stop_hardware()
            return
        try:
            while not self.shutdown_flag.is_set():
                time.sleep(0.2)
                self._tracker.poll()
        finally:
            self._stop_hardware()
