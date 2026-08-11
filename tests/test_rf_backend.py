import contextlib
import inspect
import importlib
import json
import sys
import types
import unittest
from unittest import mock


def _install_import_stubs():
    sys.modules.setdefault("ephem", types.ModuleType("ephem"))

    pigpio = types.ModuleType("pigpio")
    pigpio.OUTPUT = 0
    pigpio.pulse = lambda *args, **kwargs: (args, kwargs)
    pigpio.pi = lambda: types.SimpleNamespace(connected=True)
    sys.modules.setdefault("pigpio", pigpio)

    lgpio = types.ModuleType("lgpio")
    lgpio.TX_WAVE = 1
    sys.modules.setdefault("lgpio", lgpio)

    cc1101 = types.ModuleType("cc1101")
    sys.modules.setdefault("cc1101", cc1101)

    flask = types.ModuleType("flask")
    flask.Flask = object
    flask.render_template = lambda *args, **kwargs: ""
    flask.request = types.SimpleNamespace(url="", method="GET", values={}, headers={})
    flask.Response = lambda *args, **kwargs: None
    flask.jsonify = lambda *args, **kwargs: None
    flask.json = json
    sys.modules.setdefault("flask", flask)


_install_import_stubs()
cc1101_backend = importlib.import_module("cc1101_backend")
operateShutters = importlib.import_module("operateShutters")


class FakeConfig:
    TXGPIO = 4
    RFBackend = "raw_433"
    CC1101Frequency = 433.42
    CC1101SPIBus = 0
    CC1101SPIDevice = 0
    CC1101OutputPower = 0xC6

    def __init__(self):
        self.Shutters = {"279620": {"name": "Test", "code": 1}}

    def setCode(self, shutter_id, code):
        self.Shutters[shutter_id]["code"] = code


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


class BackendDispatchTest(unittest.TestCase):
    def setUp(self):
        FakeRadio.instances = []
        sys.modules["cc1101"].CC1101 = FakeRadio
        cc1101_backend.cc1101.CC1101 = FakeRadio

    def test_shutter_uses_imported_cc1101_module(self):
        self.assertNotIn(
            "cc1101_module",
            inspect.signature(operateShutters.Shutter).parameters,
        )

    def test_raw_433_backend_uses_existing_waveform_path(self):
        config = FakeConfig()
        config.RFBackend = "raw_433"
        transmitter = mock.Mock()
        shutter = operateShutters.Shutter(config=config, rf_transmitter=transmitter)

        shutter.sendCommand("279620", shutter.buttonUp, 2)

        transmitter.transmit.assert_called_once_with(shutter.frame, 2)
        self.assertEqual(2, config.Shutters["279620"]["code"])

    def test_cc1101_backend_configures_radio_and_reuses_waveform(self):
        config = FakeConfig()
        config.RFBackend = "cc1101"
        config.CC1101Frequency = 433.42
        config.CC1101SPIBus = 0
        config.CC1101SPIDevice = 0
        config.CC1101OutputPower = 0xC6
        shutter = operateShutters.Shutter(config=config)
        shutter.rf_transmitter.waveform_transmitter.set_idle_low = mock.Mock()
        shutter.rf_transmitter.waveform_transmitter.transmit = mock.Mock()

        shutter.sendCommand("279620", shutter.buttonDown, 3)

        self.assertEqual(1, len(FakeRadio.instances))
        radio = FakeRadio.instances[0]
        self.assertEqual(0, radio.spi_bus)
        self.assertEqual(0, radio.spi_chip_select)
        self.assertTrue(radio.lock_spi_device)
        self.assertIn(("frequency", 433.42e6), radio.calls)
        self.assertIn(("symbol_rate", 1562.5), radio.calls)
        self.assertIn(("output_power", (0, 0xC6)), radio.calls)
        self.assertLess(radio.calls.index(("async_enter",)), radio.calls.index(("async_exit",)))
        shutter.rf_transmitter.waveform_transmitter.set_idle_low.assert_called_once_with()
        shutter.rf_transmitter.waveform_transmitter.transmit.assert_called_once_with(shutter.frame, 3)
        self.assertEqual(2, config.Shutters["279620"]["code"])

    def test_cc1101_backend_reuses_transmitter_between_commands(self):
        config = FakeConfig()
        config.RFBackend = "cc1101"
        shutter = operateShutters.Shutter(config=config)

        shutter.rf_transmitter.waveform_transmitter.set_idle_low = mock.Mock()
        shutter.rf_transmitter.waveform_transmitter.transmit = mock.Mock()
        shutter.sendCommand("279620", shutter.buttonUp, 1)
        shutter.sendCommand("279620", shutter.buttonStop, 1)

        self.assertEqual(1, len(FakeRadio.instances))
        self.assertEqual(
            [mock.call(), mock.call()],
            shutter.rf_transmitter.waveform_transmitter.set_idle_low.call_args_list,
        )
        self.assertEqual(
            [mock.call(shutter.frame, 1), mock.call(shutter.frame, 1)],
            shutter.rf_transmitter.waveform_transmitter.transmit.call_args_list,
        )
        self.assertEqual(3, config.Shutters["279620"]["code"])


if __name__ == "__main__":
    unittest.main()
