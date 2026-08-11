#!/usr/bin/python3
# RF transmitter backend factory.
#
# Selects the active transmitter based on RFBackend in operateShutters.conf:
#
#   RFBackend = raw_433   (default) — original GPIO bit-bang transmitter.
#                         No extra packages needed; works on every Pi-Somfy
#                         installation without any changes.
#
#   RFBackend = cc1101    — E07-M1101D-SMA / CC1101 module driven over SPI.
#                         Requires the 'cc1101' Python package:
#                           pip install cc1101
#                         and SPI enabled on the Pi (dtparam=spi=on in
#                         config.txt). See README §2.2 for wiring and setup.
#
# If RFBackend is not set, raw_433 is used automatically, so existing
# installations continue to work with no configuration changes.

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
    # Raw433Transmitter is always constructed: CC1101 reuses it for waveform generation.
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
        "Unknown RFBackend value '" + str(backend_name) + "' in operateShutters.conf. "
        "Valid values are: raw_433 (default, no extra hardware) or cc1101 "
        "(E07-M1101D-SMA module, see README §2.2)."
    )
