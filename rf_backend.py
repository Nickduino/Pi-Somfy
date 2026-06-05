#!/usr/bin/python3

from cc1101_backend import CC1101Config
from cc1101_backend import CC1101Transmitter
from raw_433_backend import Raw433Config
from raw_433_backend import Raw433Transmitter


def get_backend_name(config):
    return getattr(config, "RFBackend", "raw_433").strip().lower()


def create_transmitter(
    config,
    is_pi5=False,
    pigpio_module=None,
    lgpio_module=None,
    lgpio_chip=4,
):
    backend_name = get_backend_name(config)
    raw_433_transmitter = Raw433Transmitter(
        Raw433Config.from_app_config(config),
        is_pi5=is_pi5,
        pigpio_module=pigpio_module,
        lgpio_module=lgpio_module,
        lgpio_chip=lgpio_chip,
    )

    if backend_name == "raw_433":
        return raw_433_transmitter
    if backend_name == "cc1101":
        return CC1101Transmitter(
            CC1101Config.from_app_config(config),
            raw_433_transmitter,
        )
    raise ValueError(
        "Unsupported RFBackend: " + str(backend_name) + ". Use raw_433 or cc1101."
    )
