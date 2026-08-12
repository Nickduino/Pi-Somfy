from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ServiceScriptTest(unittest.TestCase):
    def test_service_helpers_do_not_assume_pi_home_directory(self):
        for relative_path in ("installService.sh", "start.sh", "shutters.service"):
            content = (ROOT / relative_path).read_text()
            self.assertNotIn("/home/pi", content)
            self.assertNotIn("User=pi", content)

    def test_start_script_runs_foreground_python_process(self):
        content = (ROOT / "start.sh").read_text()

        self.assertIn("exec", content)
        self.assertNotIn("sudo /usr/bin/python3", content)
        self.assertIsNone(re.search(r"\s&\s*(?:#.*)?$", content, re.MULTILINE))

    def test_installer_generates_pi_somfy_systemd_service(self):
        content = (ROOT / "installService.sh").read_text()

        self.assertIn("BASH_SOURCE", content)
        self.assertIn("pi-somfy.service", content)
        self.assertIn("operateShutters.conf", content)


if __name__ == "__main__":
    unittest.main()
