#!/usr/bin/python3
# CC1101 RF transmitter backend (optional).
#
# Used only when RFBackend = cc1101 is set in operateShutters.conf.
# Existing installations using the raw 433 MHz GPIO transmitter do not need
# this file and can ignore it entirely — it is never imported at startup.
#
# Hardware: E07-M1101D-SMA (or any CC1101 breakout) connected over SPI.
# See README §2.2 for the full wiring table and config keys.
#
# Extra dependency (install once on the Pi before switching to this backend):
#   pip install cc1101

import time


class CC1101Config:
    # Default values match the E07-M1101D-SMA on Raspberry Pi SPI0.
    DEFAULT_FREQUENCY_MHZ = 433.42
    DEFAULT_SPI_BUS = 0
    DEFAULT_SPI_DEVICE = 0
    DEFAULT_OUTPUT_POWER = 0xC6
    DEFAULT_TRANSMIT_SETTLE_SECONDS = 0.05
    SYMBOL_RATE_BAUD = 1562.5

    def __init__(
        self,
        frequency_mhz=DEFAULT_FREQUENCY_MHZ,
        spi_bus=DEFAULT_SPI_BUS,
        spi_device=DEFAULT_SPI_DEVICE,
        output_power=DEFAULT_OUTPUT_POWER,
        transmit_settle_seconds=DEFAULT_TRANSMIT_SETTLE_SECONDS,
    ):
        self.frequency_mhz = float(frequency_mhz)
        self.spi_bus = int(spi_bus)
        self.spi_device = int(spi_device)
        self.output_power = int(output_power)
        self.transmit_settle_seconds = float(transmit_settle_seconds)
        self.symbol_rate_baud = self.SYMBOL_RATE_BAUD
        if not (400.0 <= self.frequency_mhz <= 500.0):
            raise ValueError(f"CC1101Frequency {self.frequency_mhz} MHz out of range; expected 400–500 MHz (Somfy RTS uses 433.42)")
        if not (0 <= self.output_power <= 255):
            raise ValueError(f"CC1101OutputPower {self.output_power:#x} out of range; expected 0x00–0xFF")
        if not (0.0 <= self.transmit_settle_seconds <= 1.0):
            raise ValueError(f"CC1101TransmitSettleSeconds {self.transmit_settle_seconds} out of range; expected 0.0–1.0 s")

    @classmethod
    def from_app_config(cls, config):
        if hasattr(config, "ReadValue"):
            return cls(
                frequency_mhz=config.ReadValue(
                    "CC1101Frequency",
                    return_type=float,
                    default=cls.DEFAULT_FREQUENCY_MHZ,
                    section="General",
                ),
                spi_bus=config.ReadValue(
                    "CC1101SPIBus",
                    return_type=int,
                    default=cls.DEFAULT_SPI_BUS,
                    section="General",
                ),
                spi_device=config.ReadValue(
                    "CC1101SPIDevice",
                    return_type=int,
                    default=cls.DEFAULT_SPI_DEVICE,
                    section="General",
                ),
                output_power=config.ReadValue(
                    "CC1101OutputPower",
                    return_type=int,
                    default=cls.DEFAULT_OUTPUT_POWER,
                    section="General",
                ),
                transmit_settle_seconds=config.ReadValue(
                    "CC1101TransmitSettleSeconds",
                    return_type=float,
                    default=cls.DEFAULT_TRANSMIT_SETTLE_SECONDS,
                    section="General",
                ),
            )
        return cls(
            frequency_mhz=getattr(config, "CC1101Frequency", cls.DEFAULT_FREQUENCY_MHZ),
            spi_bus=getattr(config, "CC1101SPIBus", cls.DEFAULT_SPI_BUS),
            spi_device=getattr(config, "CC1101SPIDevice", cls.DEFAULT_SPI_DEVICE),
            output_power=getattr(config, "CC1101OutputPower", cls.DEFAULT_OUTPUT_POWER),
            transmit_settle_seconds=getattr(
                config,
                "CC1101TransmitSettleSeconds",
                cls.DEFAULT_TRANSMIT_SETTLE_SECONDS,
            ),
        )

    @property
    def frequency_hz(self):
        return self.frequency_mhz * 1000000

    @property
    def output_power_table(self):
        return (0, self.output_power)


class CC1101Transmitter:
    # waveform_transmitter is a Raw433Transmitter that drives the GDO0 GPIO
    # waveform while the CC1101 holds the carrier at 433.42 MHz.
    def __init__(self, config, waveform_transmitter):
        try:
            import cc1101
        except ImportError:
            raise ImportError(
                "The 'cc1101' package is required when RFBackend = cc1101.\n"
                "Install it on the Pi with:  pip install cc1101\n"
                "Or switch back to the default by removing 'RFBackend' from "
                "operateShutters.conf (or setting it to 'raw_433')."
            ) from None
        self.config = config
        self.waveform_transmitter = waveform_transmitter
        self.radio = cc1101.CC1101(
            spi_bus=self.config.spi_bus,
            spi_chip_select=self.config.spi_device,
            lock_spi_device=True,
        )

    def __del__(self):
        try:
            if hasattr(self, "radio") and hasattr(self.radio, "__exit__"):
                self.radio.__exit__(None, None, None)
        except Exception:
            pass

    def transmit(self, frame, repetition):
        if hasattr(self.waveform_transmitter, "set_idle_low"):
            self.waveform_transmitter.set_idle_low()
        try:
            with self.radio as radio:
                radio.set_base_frequency_hertz(self.config.frequency_hz)
                radio.set_symbol_rate_baud(self.config.symbol_rate_baud)
                radio.set_output_power(self.config.output_power_table)
                with radio.asynchronous_transmission():
                    if self.config.transmit_settle_seconds > 0:
                        time.sleep(self.config.transmit_settle_seconds)
                    self.waveform_transmitter.transmit(frame, repetition)
        except Exception as e:
            raise RuntimeError(f"CC1101 transmit failed: {e}") from e
