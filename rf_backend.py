#!/usr/bin/python3

from cc1101_backend import CC1101Config
from cc1101_backend import CC1101Transmitter
from gpio_backend import GPIOConfig
from gpio_backend import GPIOTransmitter


def get_backend_name(config):
    return getattr(config, "RFBackend", "gpio").strip().lower()


def create_transmitter(
    config,
    is_pi5=False,
    pigpio_module=None,
    lgpio_module=None,
    cc1101_module=None,
    lgpio_chip=4,
):
    backend_name = get_backend_name(config)
    gpio_transmitter = GPIOTransmitter(
        GPIOConfig.from_app_config(config),
        is_pi5=is_pi5,
        pigpio_module=pigpio_module,
        lgpio_module=lgpio_module,
        lgpio_chip=lgpio_chip,
    )

    if backend_name == "gpio":
        return gpio_transmitter
    if backend_name == "cc1101":
        return CC1101Transmitter(
            CC1101Config.from_app_config(config),
            gpio_transmitter,
            cc1101_module=cc1101_module,
        )
    raise ValueError("Unsupported RFBackend: " + str(backend_name))
