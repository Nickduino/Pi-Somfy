#!/usr/bin/python3

import time

import cc1101


class CC1101Config:
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
    def __init__(self, config, waveform_transmitter):
        self.config = config
        self.waveform_transmitter = waveform_transmitter
        self.radio = cc1101.CC1101(
            spi_bus=self.config.spi_bus,
            spi_chip_select=self.config.spi_device,
            lock_spi_device=True,
        )

    def transmit(self, frame, repetition):
        if hasattr(self.waveform_transmitter, "set_idle_low"):
            self.waveform_transmitter.set_idle_low()
        with self.radio as radio:
            radio.set_base_frequency_hertz(self.config.frequency_hz)
            radio.set_symbol_rate_baud(self.config.symbol_rate_baud)
            radio.set_output_power(self.config.output_power_table)
            with radio.asynchronous_transmission():
                if self.config.transmit_settle_seconds > 0:
                    time.sleep(self.config.transmit_settle_seconds)
                self.waveform_transmitter.transmit(frame, repetition)
