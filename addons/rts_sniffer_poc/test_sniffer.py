# -*- coding: utf-8 -*-
"""Decoder unit tests (design doc §9) — run anywhere, no GPIO libraries needed:

    python3 -m unittest discover addons/rts_sniffer_poc

Synthetic edge streams are generated from the same pulse tables
Shutter.sendCommand uses (via frame_to_pulses), then fed to the decoder as
(level, timestamp_us) events exactly as the GPIO edge callbacks would deliver
them.
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sniffer import (BUTTON_DOWN, BUTTON_PROG, BUTTON_STOP, BUTTON_UP,
                     PAYLOAD_BITS, PressTracker, RTSDecoder, build_frame,
                     frame_to_pulses, pulses_to_edges)

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
        # Spec §3: XOR of all 14 nibbles of the de-obfuscated frame must be 0.
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
    on syncs and ±35 % on half-symbols (design doc §5.1)."""

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
        # daemon/kernel timestamp jitter is tens of us (design doc §10).
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
        self.assertEqual(self.ended[0][1], 4)   # repeat count retained (§5.1)

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


if __name__ == "__main__":
    unittest.main()
