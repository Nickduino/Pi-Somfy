import types
import unittest

from cc1101_backend import CC1101Transmitter
from gpio_backend import GPIOTransmitter
from rf_backend import create_transmitter


class FakeRadio:
    def __init__(self, spi_bus, spi_chip_select, lock_spi_device):
        pass


class FakePigpio:
    OUTPUT = "output"


class BackendFactoryTest(unittest.TestCase):
    def test_creates_gpio_transmitter_by_default(self):
        config = types.SimpleNamespace(RFBackend="gpio", TXGPIO=4)

        transmitter = create_transmitter(
            config,
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )

        self.assertIsInstance(transmitter, GPIOTransmitter)

    def test_creates_cc1101_transmitter_wrapping_gpio_transmitter(self):
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
            cc1101_module=types.SimpleNamespace(CC1101=FakeRadio),
        )

        self.assertIsInstance(transmitter, CC1101Transmitter)
        self.assertIsInstance(transmitter.waveform_transmitter, GPIOTransmitter)

    def test_rejects_unknown_backend(self):
        config = types.SimpleNamespace(RFBackend="other", TXGPIO=4)

        with self.assertRaisesRegex(ValueError, "Unsupported RFBackend"):
            create_transmitter(config, is_pi5=False, pigpio_module=FakePigpio())


if __name__ == "__main__":
    unittest.main()
