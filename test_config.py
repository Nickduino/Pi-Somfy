# -*- coding: utf-8 -*-
"""config.py unit tests — run anywhere, no GPIO libraries needed:

    python3 -m unittest discover

Covers RemoveValue (new in M2, needed for a real "unassign" of a
[PhysicalRemotes] entry) and WriteValue's auto-create-missing-section
behavior, using a real temp file so the exact on-disk INI text is verified,
not just the in-memory RawConfigParser view.
"""

import os
import tempfile
import unittest

from config import MyConfig


class ConfigTestCase(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".conf")
        os.close(fd)
        with open(self.path, "w") as f:
            f.write("[General]\nLogLocation = /tmp/\n\n"
                    "[Shutters]\n0x111111 = Test,True,10\n")
        self.cfg = MyConfig(filename=self.path, section="General")

    def tearDown(self):
        os.remove(self.path)

    def read_file(self):
        with open(self.path) as f:
            return f.read()


class WriteValueTests(ConfigTestCase):

    def test_write_value_auto_creates_missing_section(self):
        ok = self.cfg.WriteValue("0xaaaaaa", "shutter1,shutter2", section="PhysicalRemotes")
        self.assertTrue(ok)
        self.assertIn("[PhysicalRemotes]", self.read_file())
        self.assertEqual(
            self.cfg.ReadValue("0xaaaaaa", section="PhysicalRemotes"),
            "shutter1,shutter2")

    def test_write_value_replaces_existing_key(self):
        self.cfg.WriteValue("0x111111", "Renamed,True,20", section="Shutters")
        self.assertEqual(
            self.cfg.ReadValue("0x111111", section="Shutters"),
            "Renamed,True,20")
        # still exactly one row for this key
        rows = [k for k, v in self.cfg.GetList(section="Shutters") if k == "0x111111"]
        self.assertEqual(len(rows), 1)


class RemoveValueTests(ConfigTestCase):

    def test_remove_existing_key_deletes_line(self):
        self.cfg.WriteValue("0xaaaaaa", "shutter1", section="PhysicalRemotes")
        ok = self.cfg.RemoveValue("0xaaaaaa", section="PhysicalRemotes")
        self.assertTrue(ok)
        self.assertFalse(self.cfg.HasOption("0xaaaaaa", section="PhysicalRemotes"))
        self.assertNotIn("0xaaaaaa", self.read_file())

    def test_remove_nonexistent_key_is_idempotent(self):
        ok = self.cfg.RemoveValue("0xdeadbe", section="Shutters")
        self.assertTrue(ok)
        # unrelated existing key untouched
        self.assertTrue(self.cfg.HasOption("0x111111", section="Shutters"))

    def test_remove_from_nonexistent_section_returns_true(self):
        ok = self.cfg.RemoveValue("whatever", section="NoSuchSection")
        self.assertTrue(ok)

    def test_write_then_remove_round_trip(self):
        self.cfg.WriteValue("0xbbbbbb", "shutterX", section="PhysicalRemotes")
        self.assertEqual(
            self.cfg.ReadValue("0xbbbbbb", section="PhysicalRemotes"), "shutterX")
        self.cfg.RemoveValue("0xbbbbbb", section="PhysicalRemotes")
        self.assertIsNone(
            self.cfg.ReadValue("0xbbbbbb", section="PhysicalRemotes", default=None))

    def test_remove_does_not_disturb_other_keys_in_section(self):
        self.cfg.WriteValue("0xaaaaaa", "shutter1", section="PhysicalRemotes")
        self.cfg.WriteValue("0xbbbbbb", "shutter2", section="PhysicalRemotes")
        self.cfg.RemoveValue("0xaaaaaa", section="PhysicalRemotes")
        self.assertFalse(self.cfg.HasOption("0xaaaaaa", section="PhysicalRemotes"))
        self.assertEqual(
            self.cfg.ReadValue("0xbbbbbb", section="PhysicalRemotes"), "shutter2")


if __name__ == "__main__":
    unittest.main()
