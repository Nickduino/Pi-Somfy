import os
import tempfile
import textwrap
import unittest

from config import MyConfig


class RFConfigTest(unittest.TestCase):
    def _load_config(self, content):
        fd, path = tempfile.mkstemp(prefix="pi-somfy-test-", suffix=".conf")
        try:
            with os.fdopen(fd, "w") as config_file:
                config_file.write(textwrap.dedent(content))

            config = MyConfig(filename=path)
            self.assertTrue(config.LoadConfig())
            return config
        finally:
            os.unlink(path)

    def test_defaults_to_gpio_backend_for_existing_configs(self):
        config = self._load_config(
            """
            [General]
            LogLocation = /tmp/
            Latitude = 51.4769
            Longitude = 0
            SendRepeat = 2
            TXGPIO = 4
            UseHttps = False
            HTTPPort = 80
            HTTPSPort = 443
            RTS_Address = 0x279620

            [MQTT]
            [Shutters]
            [ShutterRollingCodes]
            [ShutterIntermediatePositions]
            [Scheduler]
            """
        )

        self.assertEqual("gpio", config.RFBackend)
        self.assertEqual(433.42, config.CC1101Frequency)
        self.assertEqual(0, config.CC1101SPIBus)
        self.assertEqual(0, config.CC1101SPIDevice)
        self.assertEqual(0xC6, config.CC1101OutputPower)

    def test_parses_cc1101_backend_options(self):
        config = self._load_config(
            """
            [General]
            LogLocation = /tmp/
            Latitude = 51.4769
            Longitude = 0
            SendRepeat = 2
            TXGPIO = 4
            RFBackend = cc1101
            CC1101Frequency = 433.42
            CC1101SPIBus = 0
            CC1101SPIDevice = 0
            CC1101OutputPower = 0xC6
            UseHttps = False
            HTTPPort = 80
            HTTPSPort = 443
            RTS_Address = 0x279620

            [MQTT]
            [Shutters]
            [ShutterRollingCodes]
            [ShutterIntermediatePositions]
            [Scheduler]
            """
        )

        self.assertEqual("cc1101", config.RFBackend)
        self.assertEqual(433.42, config.CC1101Frequency)
        self.assertEqual(0, config.CC1101SPIBus)
        self.assertEqual(0, config.CC1101SPIDevice)
        self.assertEqual(0xC6, config.CC1101OutputPower)


if __name__ == "__main__":
    unittest.main()
