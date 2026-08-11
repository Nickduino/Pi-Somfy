#!/usr/bin/python3

import time


class Raw433Config:
    DEFAULT_TXGPIO = 4

    def __init__(self, tx_gpio=DEFAULT_TXGPIO):
        if tx_gpio is None:
            tx_gpio = self.DEFAULT_TXGPIO
        self.tx_gpio = int(tx_gpio)

    @classmethod
    def from_app_config(cls, config):
        if hasattr(config, "ReadValue"):
            return cls(
                tx_gpio=config.ReadValue(
                    "TXGPIO",
                    return_type=int,
                    default=cls.DEFAULT_TXGPIO,
                    section="General",
                )
            )
        return cls(tx_gpio=getattr(config, "TXGPIO", cls.DEFAULT_TXGPIO))


class Raw433Transmitter:
    def __init__(
        self,
        config,
        is_pi5=False,
        pigpio_module=None,
        lgpio_module=None,
        lgpio_chip=4,
    ):
        self.config = config
        self.is_pi5 = is_pi5
        self.pigpio = pigpio_module
        self.lgpio = lgpio_module
        self.lgpio_chip = lgpio_chip

    def transmit(self, frame, repetition):
        if self.is_pi5:
            self._send_lgpio(frame, repetition)
        else:
            self._send_pigpio(frame, repetition)

    def set_idle_low(self):
        if self.is_pi5:
            self._set_idle_low_lgpio()
        else:
            self._set_idle_low_pigpio()

    def _load_pigpio(self):
        if self.pigpio is not None:
            return self.pigpio
        import pigpio
        return pigpio

    def _load_lgpio(self):
        if self.lgpio is not None:
            return self.lgpio
        import lgpio
        return lgpio

    def _send_pigpio(self, frame, repetition):
        pigpio = self._load_pigpio()
        pi = pigpio.pi()

        if not pi.connected:
            exit()

        tx_gpio = self.config.tx_gpio
        pi.wave_add_new()
        pi.set_mode(tx_gpio, pigpio.OUTPUT)
        pi.write(tx_gpio, 0)

        wf = []
        wf.append(pigpio.pulse(1 << tx_gpio, 0, 9415))  # wake up pulse
        wf.append(pigpio.pulse(0, 1 << tx_gpio, 89565))  # silence
        for i in range(2):  # hardware synchronization
            wf.append(pigpio.pulse(1 << tx_gpio, 0, 2560))
            wf.append(pigpio.pulse(0, 1 << tx_gpio, 2560))
        wf.append(pigpio.pulse(1 << tx_gpio, 0, 4550))  # software synchronization
        wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))

        for i in range(0, 56):  # manchester encoding of payload data
            if ((frame[int(i / 8)] >> (7 - (i % 8))) & 1):
                wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))
                wf.append(pigpio.pulse(1 << tx_gpio, 0, 640))
            else:
                wf.append(pigpio.pulse(1 << tx_gpio, 0, 640))
                wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))

        wf.append(pigpio.pulse(0, 1 << tx_gpio, 30415))  # interframe gap

        for j in range(1, repetition):  # repeating frames
            for i in range(7):  # hardware synchronization
                wf.append(pigpio.pulse(1 << tx_gpio, 0, 2560))
                wf.append(pigpio.pulse(0, 1 << tx_gpio, 2560))
            wf.append(pigpio.pulse(1 << tx_gpio, 0, 4550))  # software synchronization
            wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))

            for i in range(0, 56):  # manchester encoding of payload data
                if ((frame[int(i / 8)] >> (7 - (i % 8))) & 1):
                    wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))
                    wf.append(pigpio.pulse(1 << tx_gpio, 0, 640))
                else:
                    wf.append(pigpio.pulse(1 << tx_gpio, 0, 640))
                    wf.append(pigpio.pulse(0, 1 << tx_gpio, 640))

            wf.append(pigpio.pulse(0, 1 << tx_gpio, 30415))  # interframe gap

        pi.wave_add_generic(wf)
        wid = pi.wave_create()
        pi.wave_send_once(wid)
        while pi.wave_tx_busy():
            pass
        pi.wave_delete(wid)
        pi.stop()

    def _set_idle_low_pigpio(self):
        pigpio = self._load_pigpio()
        pi = pigpio.pi()

        if not pi.connected:
            exit()

        tx_gpio = self.config.tx_gpio
        pi.set_mode(tx_gpio, pigpio.OUTPUT)
        pi.write(tx_gpio, 0)
        pi.stop()

    def _send_lgpio(self, frame, repetition):
        lgpio = self._load_lgpio()
        tx_gpio = self.config.tx_gpio
        h = lgpio.gpiochip_open(self.lgpio_chip)
        lgpio.gpio_claim_output(h, tx_gpio, 0)

        pulses = []
        pulses.append(lgpio.pulse(1, 1, 9415))   # wake up pulse
        pulses.append(lgpio.pulse(0, 1, 89565))  # silence
        for i in range(2):  # hardware synchronization
            pulses.append(lgpio.pulse(1, 1, 2560))
            pulses.append(lgpio.pulse(0, 1, 2560))
        pulses.append(lgpio.pulse(1, 1, 4550))   # software synchronization
        pulses.append(lgpio.pulse(0, 1, 640))

        for i in range(0, 56):  # manchester encoding of payload data
            if ((frame[int(i / 8)] >> (7 - (i % 8))) & 1):
                pulses.append(lgpio.pulse(0, 1, 640))
                pulses.append(lgpio.pulse(1, 1, 640))
            else:
                pulses.append(lgpio.pulse(1, 1, 640))
                pulses.append(lgpio.pulse(0, 1, 640))

        pulses.append(lgpio.pulse(0, 1, 30415))  # interframe gap

        for j in range(1, repetition):  # repeating frames
            for i in range(7):  # hardware synchronization
                pulses.append(lgpio.pulse(1, 1, 2560))
                pulses.append(lgpio.pulse(0, 1, 2560))
            pulses.append(lgpio.pulse(1, 1, 4550))  # software synchronization
            pulses.append(lgpio.pulse(0, 1, 640))

            for i in range(0, 56):  # manchester encoding of payload data
                if ((frame[int(i / 8)] >> (7 - (i % 8))) & 1):
                    pulses.append(lgpio.pulse(0, 1, 640))
                    pulses.append(lgpio.pulse(1, 1, 640))
                else:
                    pulses.append(lgpio.pulse(1, 1, 640))
                    pulses.append(lgpio.pulse(0, 1, 640))

            pulses.append(lgpio.pulse(0, 1, 30415))  # interframe gap

        lgpio.tx_wave(h, tx_gpio, pulses)
        while lgpio.tx_busy(h, tx_gpio, lgpio.TX_WAVE):
            time.sleep(0.001)

        lgpio.gpio_free(h, tx_gpio)
        lgpio.gpiochip_close(h)

    def _set_idle_low_lgpio(self):
        lgpio = self._load_lgpio()
        tx_gpio = self.config.tx_gpio
        h = lgpio.gpiochip_open(self.lgpio_chip)
        lgpio.gpio_claim_output(h, tx_gpio, 0)
        lgpio.gpio_write(h, tx_gpio, 0)
        lgpio.gpio_free(h, tx_gpio)
        lgpio.gpiochip_close(h)
