#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RFM69-Class
sdb9696: Transmitter to emulate button press to Somfy blinds.
Based on the RFM-69 class at https://github.com/henrythasler/sdr/somfy/
"""

import pigpio as gpio

# global defines
ERROR = 1
INFO = 2
TRACE = 3

class Rfm69(object):
    """RFM69-Class"""
    # pylint: disable=too-many-instance-attributes, C0301, C0103

    def __init__(self, host="localhost", port=8888, channel=0, baudrate=10000000, debug_level=0):
        # general variables
        self.debug_level = debug_level

        # RFM69-specific variables
        self.pi = gpio.pi(host, port)
        self.handle = self.pi.spi_open(channel, baudrate, 0)    # Flags: CPOL=0 and CPHA=0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """clean up stuff"""
        self.pi.spi_close(self.handle)
        self.pi.stop()

    def debug(self, message, level=0):
        """Debug output depending on debug level."""
        if self.debug_level >= level:
            print (message)

    def read_single(self, address):
        """Read single register via spi"""
        (count, data) = self.pi.spi_xfer(self.handle, [address & 0x7F, 0x00])
        return data[1]

    def write_single(self, address, value):
        """Write single register via spi"""
        (count, data) = self.pi.spi_xfer(self.handle, [address | 0x80, value])
        return count == 2

    def write_burst(self, address, data):
        """Write bytearray of data beginning at address"""
        (count, data) = self.pi.spi_xfer(self.handle, [address | 0x80] + data)
        return count == (len(data)+1)

    def write_config(self, cfg):
        """Write cfg-tuble like this: ((register1, value1), (register2, value2), ...)"""
        for i in range(0, len(cfg)):
            reg, val = cfg[i]
            self.write_single(reg, val)
