# -*- coding: utf-8 -*-
"""Receiver unit tests — run anywhere, no GPIO libraries needed:

    python3 -m unittest discover

Decoder tests feed synthetic (level, timestamp_us) edge streams, built from
the same pulse tables Shutter.sendCommand uses, directly to RTSDecoder/
PressTracker. The remaining classes test receiver-specific behavior:
TX-pause gating, self-echo filtering, [PhysicalRemotes] group fan-out, and
the dispatch equivalence between a physical remote press and the app's own
buttons.
"""

import logging
import random
import threading
import time
import unittest

from receiver import (BUTTON_DOWN, BUTTON_PROG, BUTTON_STOP, BUTTON_UP,
                      PressTracker, Receiver, RTSDecoder, build_frame,
                      frame_to_pulses, pulses_to_edges)

logging.getLogger("test_receiver").addHandler(logging.NullHandler())
LOG = logging.getLogger("test_receiver")
LOG.setLevel(logging.CRITICAL)   # keep test output clean; correctness is asserted, not logged

# Known-good vectors generated with the *original* Shutter.sendCommand math
# from operateShutters.py — they pin the on-air encoding independently of
# build_frame, so an encoder/decoder bug pair cannot cancel out silently.
KNOWN_FRAMES = [
    (0x279620, BUTTON_UP, 1337, bytes([0xA7, 0x8F, 0x8A, 0xB3, 0x94, 0x02, 0x22])),
    (0x14A2C7, BUTTON_STOP, 42, bytes([0xA7, 0xB5, 0xB5, 0x9F, 0x8B, 0x29, 0xEE])),
    (0xDEC0DE, BUTTON_DOWN, 65535, bytes([0xA7, 0xE2, 0x1D, 0xE2, 0x3C, 0xFC, 0x22])),
]


def decode_edges(edges):
    """Feed an edge stream to a fresh decoder, return (frames, decoder)."""
    frames = []
    decoder = RTSDecoder(on_frame=frames.append)
    for level, ts in edges:
        decoder.on_edge(level, ts)
    return frames, decoder


def press_edges(address, button, code, repetitions=1, start_us=0):
    pulses = frame_to_pulses(build_frame(address, button, code), repetitions)
    return pulses_to_edges(pulses, start_us=start_us)


class BuildFrameTests(unittest.TestCase):

    def test_matches_sendcommand_vectors(self):
        for address, button, code, expected in KNOWN_FRAMES:
            self.assertEqual(bytes(build_frame(address, button, code)), expected)

    def test_deobfuscated_checksum_is_zero(self):
        # XOR of all 14 nibbles of the de-obfuscated frame must be 0.
        recv = build_frame(0x123456, BUTTON_PROG, 4242)
        plain = bytearray(recv)
        for i in range(6, 0, -1):
            plain[i] = recv[i] ^ recv[i - 1]
        checksum = 0
        for octet in plain:
            checksum ^= octet ^ (octet >> 4)
        self.assertEqual(checksum & 0x0F, 0)


class DecoderRoundTripTests(unittest.TestCase):

    def assert_decodes(self, edges, address, button, code, expected_frames=1):
        frames, decoder = decode_edges(edges)
        self.assertEqual(len(frames), expected_frames)
        for frame in frames:
            self.assertEqual(frame.address, address)
            self.assertEqual(frame.button, button)
            self.assertEqual(frame.rolling_code, code)
        self.assertEqual(decoder.checksum_failures, 0)
        return frames

    def test_single_frame_every_button(self):
        for button in (BUTTON_STOP, BUTTON_UP, BUTTON_DOWN, BUTTON_PROG):
            self.assert_decodes(press_edges(0x279620, button, 1337),
                                0x279620, button, 1337)

    def test_repeats_all_decoded(self):
        # 1 initial frame (2 hw-sync pairs) + 4 repeats (7 pairs each)
        self.assert_decodes(press_edges(0x14A2C7, BUTTON_DOWN, 500, repetitions=5),
                            0x14A2C7, BUTTON_DOWN, 500, expected_frames=5)

    def test_field_extremes(self):
        for address, code in [(0x000001, 0), (0xFFFFFF, 0xFFFF),
                              (0x800000, 1), (0x14A2C7, 0x8000)]:
            self.assert_decodes(press_edges(address, BUTTON_UP, code),
                                address, BUTTON_UP, code)

    def test_known_vector_on_air(self):
        # End to end from the sendCommand-pinned bytes, bypassing build_frame.
        for address, button, code, raw in KNOWN_FRAMES:
            edges = pulses_to_edges(frame_to_pulses(bytearray(raw)))
            self.assert_decodes(edges, address, button, code)

    def test_two_presses_back_to_back(self):
        first = press_edges(0x279620, BUTTON_UP, 10)
        second = press_edges(0x279620, BUTTON_STOP, 11,
                             start_us=first[-1][1] + 200000)
        frames, _ = decode_edges(first + second)
        self.assertEqual([(f.button, f.rolling_code) for f in frames],
                         [(BUTTON_UP, 10), (BUTTON_STOP, 11)])


class DecoderToleranceTests(unittest.TestCase):
    """Aged remote crystals drift and edges jitter; the decoder allows ±30 %
    on syncs and ±35 % on half-symbols."""

    def scaled_edges(self, scale):
        pulses = frame_to_pulses(build_frame(0x279620, BUTTON_UP, 77))
        return pulses_to_edges([(lvl, int(dur * scale)) for lvl, dur in pulses])

    def test_fast_remote_clock(self):
        frames, _ = decode_edges(self.scaled_edges(0.80))
        self.assertEqual(len(frames), 1)

    def test_slow_remote_clock(self):
        frames, _ = decode_edges(self.scaled_edges(1.25))
        self.assertEqual(len(frames), 1)

    def test_edge_jitter(self):
        # ±100 us per edge keeps every duration inside tolerance; typical
        # daemon/kernel timestamp jitter is tens of us.
        for seed in range(10):
            rng = random.Random(seed)
            edges = [(lvl, ts + rng.randint(-100, 100))
                     for lvl, ts in press_edges(0x14A2C7, BUTTON_DOWN, 900)]
            frames, _ = decode_edges(edges)
            self.assertEqual(len(frames), 1, "jitter seed %d failed" % seed)


class DecoderRobustnessTests(unittest.TestCase):

    def test_corrupted_bit_rejected_by_checksum(self):
        # A flip in the last on-air byte changes exactly one de-obfuscated
        # byte, which the nibble-XOR checksum catches. (A mid-frame flip
        # would flip the same bit in two consecutive de-obfuscated bytes and
        # cancel out of the checksum — an inherent limit of the 4-bit RTS
        # checksum, not a decoder bug.)
        frame = build_frame(0x279620, BUTTON_UP, 1337)
        frame[6] ^= 0x10
        frames, decoder = decode_edges(pulses_to_edges(frame_to_pulses(frame)))
        self.assertEqual(frames, [])
        self.assertEqual(decoder.checksum_failures, 1)

    def test_truncated_frame_then_valid_frame(self):
        full = press_edges(0x279620, BUTTON_UP, 1)
        truncated = full[:40]   # cut mid-payload, then 100 ms of silence
        valid = press_edges(0x279620, BUTTON_DOWN, 2,
                            start_us=truncated[-1][1] + 100000)
        frames, decoder = decode_edges(truncated + valid)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].button, BUTTON_DOWN)
        self.assertEqual(frames[0].rolling_code, 2)
        self.assertGreaterEqual(decoder.payload_aborts, 1)

    def test_noise_produces_no_frames(self):
        rng = random.Random(1234)
        edges, t, level = [], 0, 0
        for _ in range(5000):
            level ^= 1
            t += rng.randint(200, 3500)
            edges.append((level, t))
        frames, decoder = decode_edges(edges)
        self.assertEqual(frames, [])
        self.assertEqual(decoder.checksum_failures, 0)

    def test_frame_decoded_after_noise(self):
        rng = random.Random(99)
        edges, t, level = [], 0, 0
        for _ in range(500):
            level ^= 1
            t += rng.randint(200, 3500)
            edges.append((level, t))
        if level == 1:          # let the line settle low before the frame
            t += 5000
            edges.append((0, t))
        edges += press_edges(0x14A2C7, BUTTON_STOP, 33, start_us=t + 50000)
        frames, _ = decode_edges(edges)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].address, 0x14A2C7)

    def test_single_hw_sync_pair_rejected(self):
        # Fewer than 2 hardware-sync pairs must not enter payload collection.
        pulses = frame_to_pulses(build_frame(0x279620, BUTTON_UP, 5))
        del pulses[2:4]          # drop one of the two initial sync pairs
        frames, _ = decode_edges(pulses_to_edges(pulses))
        self.assertEqual(frames, [])

    def test_duplicate_level_edge_resyncs(self):
        edges = press_edges(0x279620, BUTTON_UP, 7)
        decoder_frames = []
        decoder = RTSDecoder(on_frame=decoder_frames.append)
        decoder.on_edge(0, 0)    # spurious same-level event before the press
        decoder.on_edge(0, 1000)
        for level, ts in [(lvl, ts + 10000) for lvl, ts in edges]:
            decoder.on_edge(level, ts)
        self.assertEqual(len(decoder_frames), 1)


class PressTrackerTests(unittest.TestCase):

    def setUp(self):
        self.now = 0.0
        self.presses = []
        self.ended = []
        self.tracker = PressTracker(
            on_press=lambda f: self.presses.append(f),
            on_press_end=lambda f, r: self.ended.append((f, r)),
            clock=lambda: self.now)
        self.decoder = RTSDecoder(on_frame=self.tracker.on_frame)

    def feed_press(self, address, button, code, repetitions, start_us=0):
        for level, ts in press_edges(address, button, code, repetitions, start_us):
            self.decoder.on_edge(level, ts)

    def test_repeats_collapse_into_one_press(self):
        self.feed_press(0x14A2C7, BUTTON_UP, 1337, repetitions=4)
        self.assertEqual(len(self.presses), 1)
        self.assertEqual(self.presses[0].rolling_code, 1337)
        self.now = 1.0           # quiet period elapsed
        self.tracker.poll()
        self.assertEqual(len(self.ended), 1)
        self.assertEqual(self.ended[0][1], 4)   # repeat count retained

    def test_new_rolling_code_is_new_press(self):
        self.feed_press(0x14A2C7, BUTTON_UP, 1, repetitions=2)
        self.now = 0.5
        self.feed_press(0x14A2C7, BUTTON_UP, 2, repetitions=2, start_us=10**7)
        self.assertEqual(len(self.presses), 2)
        self.assertEqual(len(self.ended), 1)    # first press flushed by second
        self.assertEqual(self.ended[0][1], 2)

    def test_ttl_expiry_splits_presses(self):
        self.feed_press(0x14A2C7, BUTTON_STOP, 9, repetitions=1)
        self.now = 5.0           # past the 3 s TTL: same key counts as new press
        self.feed_press(0x14A2C7, BUTTON_STOP, 9, repetitions=1, start_us=5 * 10**6)
        self.assertEqual(len(self.presses), 2)


# ── Receiver integration: TX-gate, self-echo, [PhysicalRemotes] fan-out ─────

class FakeShutter(object):
    """Minimal Shutter stand-in exposing only what Receiver touches."""

    def __init__(self):
        self.transmitting = threading.Event()
        self.commands = []   # [(shutterId, button), ...]

    def recordExternalCommand(self, shutterId, button):
        self.commands.append((shutterId, button))


class FakeConfig(object):

    def __init__(self, shutters=None, physical_remotes=None):
        self.Shutters = shutters or {}
        self.PhysicalRemotes = physical_remotes or {}
        self.RXGPIO = None
        self.RXSpiSCK = None
        self.RXSpiMOSI = None
        self.RXSpiMISO = None
        self.RXSpiCSN = None


def make_receiver(shutters=None, physical_remotes=None):
    shutter = FakeShutter()
    config = FakeConfig(shutters, physical_remotes)
    receiver = Receiver(kwargs={'log': LOG, 'shutter': shutter, 'config': config})
    return receiver, shutter, config


class TxGateTests(unittest.TestCase):

    def test_edges_dropped_while_transmitting(self):
        receiver, shutter, _ = make_receiver()
        shutter.transmitting.set()
        for level, ts in press_edges(0x111111, BUTTON_UP, 1):
            receiver._on_edge(level, ts)
        self.assertEqual(receiver._decoder.frames_decoded, 0)
        self.assertEqual(shutter.commands, [])

    def test_decoder_resets_after_gated_partial_frame(self):
        receiver, shutter, _ = make_receiver(
            shutters={"0x02aaaa": {}},
            physical_remotes={"0x222222": ["0x02aaaa"]})

        shutter.transmitting.set()
        interrupted = press_edges(0x111111, BUTTON_UP, 1)
        midpoint = len(interrupted) // 2
        for level, ts in interrupted[:midpoint]:
            receiver._on_edge(level, ts)     # dropped: gated
        shutter.transmitting.clear()
        for level, ts in interrupted[midpoint:]:
            receiver._on_edge(level, ts)     # tail arrives post-gate; must not wedge the decoder
        self.assertEqual(shutter.commands, [])

        # A subsequent, unrelated, complete press must still decode cleanly —
        # proving the decoder was reset rather than left mid-payload.
        next_press = press_edges(0x222222, BUTTON_STOP, 2,
                                 start_us=interrupted[-1][1] + 200000)
        for level, ts in next_press:
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands, [("0x02aaaa", BUTTON_STOP)])


class SelfEchoTests(unittest.TestCase):

    def test_own_shutter_address_is_dropped(self):
        receiver, shutter, _ = make_receiver(shutters={"0x111111": {}})
        for level, ts in press_edges(0x111111, BUTTON_UP, 1):
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands, [])

    def test_other_address_is_not_dropped(self):
        receiver, shutter, _ = make_receiver(
            shutters={"0x111111": {}, "0x02aaaa": {}},
            physical_remotes={"0x222222": ["0x02aaaa"]})
        for level, ts in press_edges(0x222222, BUTTON_DOWN, 1):
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands, [("0x02aaaa", BUTTON_DOWN)])


class PhysicalRemotesFanOutTests(unittest.TestCase):

    def test_group_fans_out_to_every_shutter(self):
        receiver, shutter, _ = make_receiver(
            shutters={"0x02aaaa": {}, "0x02bbbb": {}},
            physical_remotes={"0x279620": ["0x02aaaa", "0x02bbbb"]})
        for level, ts in press_edges(0x279620, BUTTON_DOWN, 42):
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands,
                        [("0x02aaaa", BUTTON_DOWN), ("0x02bbbb", BUTTON_DOWN)])

    def test_unknown_remote_is_recorded_not_dispatched(self):
        receiver, shutter, _ = make_receiver()
        for level, ts in press_edges(0xABCDEF, BUTTON_UP, 1):
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands, [])
        self.assertEqual(len(receiver._unknown_remotes), 1)
        self.assertEqual(receiver._unknown_remotes[0][0], "0xabcdef")

    def test_unmapped_shutter_id_in_group_is_skipped(self):
        receiver, shutter, _ = make_receiver(
            shutters={"0x02aaaa": {}},   # 0x02cccc deliberately absent
            physical_remotes={"0x279620": ["0x02aaaa", "0x02cccc"]})
        for level, ts in press_edges(0x279620, BUTTON_UP, 1):
            receiver._on_edge(level, ts)
        self.assertEqual(shutter.commands, [("0x02aaaa", BUTTON_UP)])


# ── Simulation equivalence: physical remote vs. app button ──────────────────
# Needs the real Shutter class, which means operateShutters.py's full
# requirements.txt (ephem, pigpio/lgpio, Flask, paho-mqtt) — unlike the pure
# decoder tests above, this isn't optional-dependency-light, so skip cleanly
# if those aren't installed rather than failing collection for the whole file.
try:
    from operateShutters import Shutter
    _HAVE_SHUTTER = True
except Exception:
    _HAVE_SHUTTER = False


@unittest.skipUnless(_HAVE_SHUTTER, "operateShutters and its dependencies "
                     "(ephem, pigpio/lgpio, Flask, paho-mqtt) are required "
                     "to test Shutter directly")
class SimulationEquivalenceTests(unittest.TestCase):
    """recordExternalCommand (physical-remote path) must dispatch to exactly
    the same _simulate* methods rise()/lower()/stop() use — a
    physical press updates the position model identically to the equivalent
    app button, minus the RF transmission."""

    class _FakeConfig(object):
        def __init__(self, shutters):
            self.TXGPIO = None
            self.ShutterPositions = {}
            self.Shutters = shutters
            self.SendRepeat = 1

        def WriteValue(self, entry, value, section=None):
            pass

    def _make_shutter(self):
        shutters = {"0x02aaaa": {"name": "test", "durationDown": 20,
                                 "durationUp": 20, "intermediatePosition": None}}
        return Shutter(log=LOG, config=self._FakeConfig(shutters))

    def test_up_button_dispatches_to_simulate_up(self):
        shutter = self._make_shutter()
        calls = []
        shutter._simulateUp = lambda shutterId: calls.append(shutterId)
        shutter.recordExternalCommand("0x02aaaa", Shutter.buttonUp)
        self.assertEqual(calls, ["0x02aaaa"])

    def test_down_button_dispatches_to_simulate_down(self):
        shutter = self._make_shutter()
        calls = []
        shutter._simulateDown = lambda shutterId: calls.append(shutterId)
        shutter.recordExternalCommand("0x02aaaa", Shutter.buttonDown)
        self.assertEqual(calls, ["0x02aaaa"])

    def test_stop_button_dispatches_to_simulate_stop(self):
        shutter = self._make_shutter()
        calls = []
        shutter._simulateStop = lambda shutterId: calls.append(shutterId)
        shutter.recordExternalCommand("0x02aaaa", Shutter.buttonStop)
        self.assertEqual(calls, ["0x02aaaa"])


@unittest.skipUnless(_HAVE_SHUTTER, "operateShutters and its dependencies "
                     "(ephem, pigpio/lgpio, Flask, paho-mqtt) are required "
                     "to test Shutter directly")
class MovementCallbackTests(unittest.TestCase):
    """registerMovementCallBack fires 'opening'/'closing'/'stopped' for both
    the TX/software path and the physical-remote path identically (M2 §5.4)."""

    class _FakeConfig(object):
        def __init__(self, shutters):
            self.TXGPIO = None
            self.ShutterPositions = {}
            self.Shutters = shutters
            self.SendRepeat = 1

        def WriteValue(self, entry, value, section=None):
            pass

    def _make_shutter(self, duration=20, intermediatePosition=None):
        shutters = {"0x02aaaa": {"name": "test", "durationDown": duration,
                                 "durationUp": duration,
                                 "intermediatePosition": intermediatePosition}}
        shutter = Shutter(log=LOG, config=self._FakeConfig(shutters))
        shutter.sendCommand = lambda *a, **kw: None   # never touch real hardware
        self.events = []
        shutter.registerMovementCallBack(
            lambda shutterId, state: self.events.append(("movement", state)))
        shutter.registerCallBack(
            lambda shutterId, position: self.events.append(("position", position)))
        return shutter

    def movements(self):
        return [e[1] for e in self.events if e[0] == "movement"]

    def test_simulate_up_fires_opening_immediately(self):
        shutter = self._make_shutter()
        shutter._simulateUp("0x02aaaa")
        self.assertEqual(self.movements(), ["opening"])

    def test_get_movement_state_reflects_last_fired_event(self):
        shutter = self._make_shutter()
        self.assertIsNone(shutter.getMovementState("0x02aaaa"))
        # Start mid-travel: at position 0 (or 100), the very next _simulateUp/
        # _simulateDown call computes a near-zero timeToWait for its spawned
        # settle thread (already at the target end), which can race ahead and
        # fire 'stopped' before this test's own assertions run.
        shutter.getShutterState("0x02aaaa", 50)
        shutter._simulateUp("0x02aaaa")
        self.assertEqual(shutter.getMovementState("0x02aaaa"), "opening")
        shutter._simulateDown("0x02aaaa")
        self.assertEqual(shutter.getMovementState("0x02aaaa"), "closing")

    def test_simulate_down_fires_closing_immediately(self):
        shutter = self._make_shutter()
        shutter._simulateDown("0x02aaaa")
        self.assertEqual(self.movements(), ["closing"])

    def test_simulate_stop_normal_fires_stopped_before_position_settles(self):
        shutter = self._make_shutter(duration=100)
        state = shutter.getShutterState("0x02aaaa", 50)
        state.registerCommand('up')
        shutter._fireMovement("0x02aaaa", 'opening')   # mark as genuinely moving
        self.events = []   # discard the setup event above; assert only on _simulateStop's own effects
        state.lastCommandTime = time.monotonic() - 1.0   # ~1s into a 100s travel
        shutter._simulateStop("0x02aaaa")
        self.assertEqual(self.movements(), ["stopped"])
        # The movement event must precede the position-settle event, so a
        # more-precise open/closed publish (from the position callback)
        # always has the last word on the retained MQTT topic.
        self.assertEqual([e[0] for e in self.events], ["movement", "position"])

    def test_simulate_stop_intermediate_fallback_fires_closing_not_stopped(self):
        # position (80) above the stored MY position (30): motor moves down.
        shutter = self._make_shutter(duration=20, intermediatePosition=30)
        shutter.getShutterState("0x02aaaa", 80)
        shutter._simulateStop("0x02aaaa")
        self.assertEqual(self.movements(), ["closing"])

    def test_simulate_stop_intermediate_fallback_fires_opening_not_stopped(self):
        # position (30) below the stored MY position (80): motor moves up.
        shutter = self._make_shutter(duration=20, intermediatePosition=80)
        shutter.getShutterState("0x02aaaa", 30)
        shutter._simulateStop("0x02aaaa")
        self.assertEqual(self.movements(), ["opening"])

    def test_simulate_stop_stationary_fallback_fires_stopped(self):
        shutter = self._make_shutter(duration=20, intermediatePosition=None)
        shutter.getShutterState("0x02aaaa", 50)
        shutter._simulateStop("0x02aaaa")
        self.assertEqual(self.movements(), ["stopped"])

    def test_stop_after_settled_partial_move_goes_to_my_position(self):
        # Regression: _simulateStop used to infer "still moving" from
        # elapsed-time-since-last-command vs. the shutter's FULL duration —
        # which wrongly matched here, since a partial move settles in far
        # less time than the full duration. A MY press shortly afterward
        # must correctly see the shutter as already stopped and evaluate
        # the MY-position fallback, not compute a bogus interrupted-move
        # position as if it were still rising.
        shutter = self._make_shutter(duration=20, intermediatePosition=45)
        # Drive the same state transitions risePartial(shutterId, 60) would
        # (registerCommand -> 'opening' -> 'stopped' + setPosition), without
        # its real time.sleep(...) — risePartial blocks synchronously for the
        # move's duration, unlike _simulateUp/_simulateDown which settle on a
        # background thread, so calling it here would make this test take
        # (60/100)*20s = 12 real seconds.
        state = shutter.getShutterState("0x02aaaa", 0)
        state.registerCommand('up')
        shutter._fireMovement("0x02aaaa", 'opening')
        shutter._fireMovement("0x02aaaa", 'stopped')
        shutter.setPosition("0x02aaaa", 60)
        self.assertEqual(shutter.getPosition("0x02aaaa"), 60)
        self.events = []
        shutter._simulateStop("0x02aaaa")
        # 60 -> intermediatePosition 45 is a move down (closing), not the
        # bogus "still opening" interpolation the old elapsed-time
        # heuristic would have produced.
        self.assertEqual(self.movements(), ["closing"])

    def test_rise_partial_fires_opening_then_stopped(self):
        shutter = self._make_shutter(duration=0)
        shutter.risePartial("0x02aaaa", 80)
        self.assertEqual(self.movements(), ["opening", "stopped"])

    def test_lower_partial_fires_closing_then_stopped(self):
        shutter = self._make_shutter(duration=0)
        shutter.lowerPartial("0x02aaaa", 20)
        self.assertEqual(self.movements(), ["closing", "stopped"])

    def test_record_external_command_up_fires_same_event_as_simulate_up(self):
        shutter = self._make_shutter()
        shutter.recordExternalCommand("0x02aaaa", Shutter.buttonUp)
        self.assertEqual(self.movements(), ["opening"])

    def test_full_move_fires_stopped_when_it_completes_naturally(self):
        # waitAndSetFinalPosition's background thread (spawned by
        # _simulateUp/_simulateDown for a full, uninterrupted move) must
        # clear 'opening'/'closing' back to 'stopped' once it reaches 100/0
        # — this is the only path that settles without an explicit stop
        # command, so nothing else fires this event for it.
        shutter = self._make_shutter(duration=0.05)
        shutter._simulateUp("0x02aaaa")
        for _ in range(50):
            if self.movements() == ["opening", "stopped"]:
                break
            time.sleep(0.02)
        self.assertEqual(self.movements(), ["opening", "stopped"])

    def test_display_position_equals_settled_position_when_stationary(self):
        shutter = self._make_shutter()
        shutter.getShutterState("0x02aaaa", 42)
        self.assertEqual(shutter.getDisplayPosition("0x02aaaa"), 42)

    def test_display_position_interpolates_while_opening(self):
        shutter = self._make_shutter(duration=100)
        state = shutter.getShutterState("0x02aaaa", 0)
        state.registerCommand('up')
        shutter._fireMovement("0x02aaaa", 'opening')
        state.lastCommandTime = time.monotonic() - 25.0   # 25% into a 100s move
        self.assertEqual(shutter.getDisplayPosition("0x02aaaa"), 25)

    def test_display_position_interpolates_while_closing(self):
        shutter = self._make_shutter(duration=100)
        state = shutter.getShutterState("0x02aaaa", 100)
        state.registerCommand('down')
        shutter._fireMovement("0x02aaaa", 'closing')
        state.lastCommandTime = time.monotonic() - 30.0   # 30% into a 100s move
        self.assertEqual(shutter.getDisplayPosition("0x02aaaa"), 70)

    def test_display_position_reports_target_once_elapsed_exceeds_duration(self):
        # Right before waitAndSetFinalPosition's background thread actually
        # settles (a real race window), a poll should report the target
        # (100/0), not the stale pre-move position.
        shutter = self._make_shutter(duration=10)
        state = shutter.getShutterState("0x02aaaa", 0)
        state.registerCommand('up')
        shutter._fireMovement("0x02aaaa", 'opening')
        state.lastCommandTime = time.monotonic() - 15.0   # already past the 10s duration
        self.assertEqual(shutter.getDisplayPosition("0x02aaaa"), 100)

    def test_display_position_interpolates_during_my_position_fallback_move(self):
        # STOP/MY pressed while stationary and away from the stored MY
        # position (the bug report this is fixing): the motor moves toward
        # intermediatePosition, and getDisplayPosition should track it live,
        # not just show the stale starting position until it settles.
        shutter = self._make_shutter(duration=20, intermediatePosition=30)
        shutter.getShutterState("0x02aaaa", 80)   # above the MY position -> closing
        shutter._simulateStop("0x02aaaa")
        self.assertEqual(self.movements(), ["closing"])
        state = shutter.getShutterState("0x02aaaa")
        # 5s at the configured 100/20=5%/s rate -> 25 points off 80, landing
        # mid-travel toward (not yet at) the 30 target — this move's actual
        # full duration (per _simulateStop's own math) is 10s (50 points at
        # 5%/s), so 5s in is genuinely halfway there, not coincidentally at
        # the destination.
        state.lastCommandTime = time.monotonic() - 5.0
        self.assertEqual(shutter.getDisplayPosition("0x02aaaa"), 55)


if __name__ == "__main__":
    unittest.main()
