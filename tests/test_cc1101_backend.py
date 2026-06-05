import contextlib
import types
import unittest

from cc1101_backend import CC1101Config, CC1101Transmitter


class FakeRadio:
    instances = []

    def __init__(self, spi_bus, spi_chip_select, lock_spi_device):
        self.spi_bus = spi_bus
        self.spi_chip_select = spi_chip_select
        self.lock_spi_device = lock_spi_device
        self.calls = []
        FakeRadio.instances.append(self)

    def __enter__(self):
        self.calls.append(("enter",))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.calls.append(("exit", exc_type))
        return False

    def set_base_frequency_hertz(self, frequency_hertz):
        self.calls.append(("frequency", frequency_hertz))

    def set_symbol_rate_baud(self, symbol_rate):
        self.calls.append(("symbol_rate", symbol_rate))

    def set_output_power(self, output_power):
        self.calls.append(("output_power", tuple(output_power)))

    @contextlib.contextmanager
    def asynchronous_transmission(self):
        self.calls.append(("async_enter",))
        yield "GDO0"
        self.calls.append(("async_exit",))


class CC1101BackendTest(unittest.TestCase):
    def setUp(self):
        FakeRadio.instances = []

    def test_config_is_derived_from_app_config(self):
        app_config = types.SimpleNamespace(
            CC1101Frequency=433.42,
            CC1101SPIBus=0,
            CC1101SPIDevice=1,
            CC1101OutputPower=0xC6,
        )

        config = CC1101Config.from_app_config(app_config)

        self.assertEqual(433.42e6, config.frequency_hz)
        self.assertEqual(0, config.spi_bus)
        self.assertEqual(1, config.spi_device)
        self.assertEqual(0xC6, config.output_power)
        self.assertEqual(1562.5, config.symbol_rate_baud)

    def test_config_reads_values_from_myconfig_interface(self):
        class AppConfig:
            def ReadValue(self, entry, return_type=str, default=None, section=None):
                values = {
                    "CC1101Frequency": "433.42",
                    "CC1101SPIBus": "0",
                    "CC1101SPIDevice": "1",
                    "CC1101OutputPower": "0xC6",
                }
                value = values.get(entry)
                if value is None:
                    return default
                if return_type == int:
                    return int(value, 0)
                if return_type == float:
                    return float(value)
                return value

        config = CC1101Config.from_app_config(AppConfig())

        self.assertEqual(433.42e6, config.frequency_hz)
        self.assertEqual(0, config.spi_bus)
        self.assertEqual(1, config.spi_device)
        self.assertEqual(0xC6, config.output_power)

    def test_transmitter_configures_radio_and_calls_waveform_callback(self):
        fake_cc1101 = types.SimpleNamespace(CC1101=FakeRadio)
        config = CC1101Config(
            frequency_mhz=433.42,
            spi_bus=0,
            spi_device=0,
            output_power=0xC6,
        )
        calls = []

        transmitter = CC1101Transmitter(config, cc1101_module=fake_cc1101)
        transmitter.transmit(lambda repetition: calls.append(("waveform", repetition)), 3)

        self.assertEqual([("waveform", 3)], calls)
        self.assertEqual(1, len(FakeRadio.instances))
        radio = FakeRadio.instances[0]
        self.assertEqual(0, radio.spi_bus)
        self.assertEqual(0, radio.spi_chip_select)
        self.assertTrue(radio.lock_spi_device)
        self.assertEqual(
            [
                ("enter",),
                ("frequency", 433.42e6),
                ("symbol_rate", 1562.5),
                ("output_power", (0, 0xC6)),
                ("async_enter",),
                ("async_exit",),
                ("exit", None),
            ],
            radio.calls,
        )

    def test_transmitter_reuses_radio_object_between_transmits(self):
        fake_cc1101 = types.SimpleNamespace(CC1101=FakeRadio)
        config = CC1101Config()
        calls = []

        transmitter = CC1101Transmitter(config, cc1101_module=fake_cc1101)
        transmitter.transmit(lambda repetition: calls.append(("waveform", repetition)), 1)
        transmitter.transmit(lambda repetition: calls.append(("waveform", repetition)), 2)

        self.assertEqual([("waveform", 1), ("waveform", 2)], calls)
        self.assertEqual(1, len(FakeRadio.instances))


if __name__ == "__main__":
    unittest.main()
