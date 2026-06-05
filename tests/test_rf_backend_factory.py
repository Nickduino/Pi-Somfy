import inspect
import sys
import types
import unittest

fake_cc1101 = types.ModuleType("cc1101")
sys.modules["cc1101"] = fake_cc1101

from cc1101_backend import CC1101Transmitter
import cc1101_backend
from raw_433_backend import Raw433Transmitter
from rf_backend import create_transmitter
from rf_backend import get_backend_name


class FakeRadio:
    def __init__(self, spi_bus, spi_chip_select, lock_spi_device):
        pass


class FakePigpio:
    OUTPUT = "output"


class BackendFactoryTest(unittest.TestCase):
    def setUp(self):
        fake_cc1101.CC1101 = FakeRadio
        cc1101_backend.cc1101.CC1101 = FakeRadio

    def test_factory_uses_imported_cc1101_module(self):
        self.assertNotIn(
            "cc1101_module",
            inspect.signature(create_transmitter).parameters,
        )

    def test_creates_raw_433_transmitter_by_default(self):
        config = types.SimpleNamespace(RFBackend="raw_433", TXGPIO=4)

        transmitter = create_transmitter(
            config,
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )

        self.assertIsInstance(transmitter, Raw433Transmitter)

    def test_accepts_legacy_gpio_backend_alias(self):
        config = types.SimpleNamespace(RFBackend="gpio", TXGPIO=4)

        transmitter = create_transmitter(
            config,
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )

        self.assertEqual("raw_433", get_backend_name(config))
        self.assertIsInstance(transmitter, Raw433Transmitter)

    def test_creates_cc1101_transmitter_wrapping_raw_433_transmitter(self):
        config = types.SimpleNamespace(
            RFBackend="cc1101",
            TXGPIO=4,
            CC1101Frequency=433.42,
            CC1101SPIBus=0,
            CC1101SPIDevice=0,
            CC1101OutputPower=0xC6,
        )

        transmitter = create_transmitter(
            config,
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )

        self.assertIsInstance(transmitter, CC1101Transmitter)
        self.assertIsInstance(transmitter.waveform_transmitter, Raw433Transmitter)

    def test_rejects_unknown_backend(self):
        config = types.SimpleNamespace(RFBackend="other", TXGPIO=4)

        with self.assertRaisesRegex(ValueError, "Unsupported RFBackend"):
            create_transmitter(config, is_pi5=False, pigpio_module=FakePigpio())


if __name__ == "__main__":
    unittest.main()
