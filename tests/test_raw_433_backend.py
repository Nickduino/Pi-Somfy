import unittest

from raw_433_backend import Raw433Config, Raw433Transmitter


class FakePi:
    instances = []

    def __init__(self):
        self.connected = True
        self.calls = []
        FakePi.instances.append(self)

    def wave_add_new(self):
        self.calls.append(("wave_add_new",))

    def set_mode(self, gpio, mode):
        self.calls.append(("set_mode", gpio, mode))

    def write(self, gpio, level):
        self.calls.append(("write", gpio, level))

    def wave_add_generic(self, waveform):
        self.calls.append(("wave_add_generic", waveform))

    def wave_create(self):
        self.calls.append(("wave_create",))
        return 7

    def wave_send_once(self, wave_id):
        self.calls.append(("wave_send_once", wave_id))

    def wave_tx_busy(self):
        self.calls.append(("wave_tx_busy",))
        return False

    def wave_delete(self, wave_id):
        self.calls.append(("wave_delete", wave_id))

    def stop(self):
        self.calls.append(("stop",))


class FakePigpio:
    OUTPUT = "output"

    def pi(self):
        return FakePi()

    def pulse(self, gpio_on, gpio_off, delay):
        return ("pulse", gpio_on, gpio_off, delay)


class FakeLgpio:
    TX_WAVE = "tx_wave"

    def __init__(self):
        self.calls = []

    def gpiochip_open(self, chip):
        self.calls.append(("gpiochip_open", chip))
        return "handle"

    def gpio_claim_output(self, handle, gpio, level=0):
        self.calls.append(("gpio_claim_output", handle, gpio, level))

    def gpio_write(self, handle, gpio, level):
        self.calls.append(("gpio_write", handle, gpio, level))


    def pulse(self, level, mask, delay):
        return ("pulse", level, mask, delay)

    def tx_wave(self, handle, gpio, pulses):
        self.calls.append(("tx_wave", handle, gpio, pulses))

    def tx_busy(self, handle, gpio, tx_type):
        self.calls.append(("tx_busy", handle, gpio, tx_type))
        return False

    def gpio_free(self, handle, gpio):
        self.calls.append(("gpio_free", handle, gpio))

    def gpiochip_close(self, handle):
        self.calls.append(("gpiochip_close", handle))


class Raw433BackendTest(unittest.TestCase):
    def setUp(self):
        FakePi.instances = []

    def test_config_reads_tx_gpio_from_app_config(self):
        class AppConfig:
            def ReadValue(self, entry, return_type=str, default=None, section=None):
                if entry == "TXGPIO":
                    return 17
                return default

        config = Raw433Config.from_app_config(AppConfig())

        self.assertEqual(17, config.tx_gpio)

    def test_config_uses_default_gpio_when_config_value_is_none(self):
        config = Raw433Config(tx_gpio=None)

        self.assertEqual(4, config.tx_gpio)

    def test_pigpio_transmitter_sends_waveform(self):
        transmitter = Raw433Transmitter(
            Raw433Config(tx_gpio=4),
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )
        frame = bytearray([0] * 7)

        transmitter.transmit(frame, 1)

        fake_pi = FakePi.instances[0]
        self.assertIn(("set_mode", 4, "output"), fake_pi.calls)
        self.assertIn(("write", 4, 0), fake_pi.calls)
        wave_call = [call for call in fake_pi.calls if call[0] == "wave_add_generic"][0]
        waveform = wave_call[1]
        self.assertEqual(("pulse", 1 << 4, 0, 9415), waveform[0])
        self.assertIn(("wave_send_once", 7), fake_pi.calls)
        self.assertIn(("stop",), fake_pi.calls)

    def test_pigpio_transmitter_can_set_idle_low(self):
        transmitter = Raw433Transmitter(
            Raw433Config(tx_gpio=4),
            is_pi5=False,
            pigpio_module=FakePigpio(),
        )

        transmitter.set_idle_low()

        fake_pi = FakePi.instances[0]
        self.assertEqual(
            [("set_mode", 4, "output"), ("write", 4, 0), ("stop",)],
            fake_pi.calls,
        )

    def test_lgpio_transmitter_sends_waveform(self):
        fake_lgpio = FakeLgpio()
        transmitter = Raw433Transmitter(
            Raw433Config(tx_gpio=4),
            is_pi5=True,
            lgpio_module=fake_lgpio,
            lgpio_chip=4,
        )
        frame = bytearray([0] * 7)

        transmitter.transmit(frame, 1)

        self.assertEqual(("gpiochip_open", 4), fake_lgpio.calls[0])
        self.assertEqual(("gpio_claim_output", "handle", 4, 0), fake_lgpio.calls[1])
        tx_wave_call = [call for call in fake_lgpio.calls if call[0] == "tx_wave"][0]
        self.assertEqual("handle", tx_wave_call[1])
        self.assertEqual(4, tx_wave_call[2])
        self.assertEqual(("pulse", 1, 1, 9415), tx_wave_call[3][0])

    def test_lgpio_transmitter_can_set_idle_low(self):
        fake_lgpio = FakeLgpio()
        transmitter = Raw433Transmitter(
            Raw433Config(tx_gpio=4),
            is_pi5=True,
            lgpio_module=fake_lgpio,
            lgpio_chip=4,
        )

        transmitter.set_idle_low()

        self.assertEqual(
            [
                ("gpiochip_open", 4),
                ("gpio_claim_output", "handle", 4, 0),
                ("gpio_write", "handle", 4, 0),
                ("gpio_free", "handle", 4),
                ("gpiochip_close", "handle"),
            ],
            fake_lgpio.calls,
        )


if __name__ == "__main__":
    unittest.main()
