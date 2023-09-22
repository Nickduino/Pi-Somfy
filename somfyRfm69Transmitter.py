#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sdb9696: Transmitter to emulate button press to Somfy blinds.
Initially based on the transmitter.py from https://github.com/henrythasler/sdr/blob/master/somfy/transmitter.py
Modified to use the wavefrom creation logic from https://github.com/Nickduino/Pi-Somfy/.  The waveform logic 
in the original of this files works but as I've forked Nickduino it's best to have only one way to create the
waveform.  N.B. the two methods treated the address parameter differently as henrythasler reversed the order of 
bytes.  I'm not sure which is correct but it doesn't as only using a single implementation.
Also updated to fix the frequency to use 433.42 MHz as the original calculation was a bit off.

If someone wanted to use this transmitter independantly of the rest of the Nickduino functionality only 
the following files are needed:

    rfm69.py
    SomfyRtsWaveForm.py
    somfyRfm68Transmitter.py (this file)
"""

import sys

from time import sleep
import pigpio as gpio
from rfm69 import Rfm69
import json
from somfyRtsWaveForm import createWaveForm

# define pigpio GPIO-pins where self.RESETPIN- and self.DATAPIN-Pin of RFM69-Transceiver are connected
RESETPINDEFAULT = 25
DATAPINDEFAULT = 26

class SomfyRfm69Tx(object):

    # define pigpio-host 
    HOST = "localhost"
   

    config=None

    clock = 640    

    def __init__(self, resetBcmPinNumber = RESETPINDEFAULT, dataBcmPinNumber = DATAPINDEFAULT, pigpiohost="localhost", pigpioport=8888, spichannel=0, spibaudrate=32000):

        self.piconnected = False

        self.pi = gpio.pi(pigpiohost, pigpioport)
        self.RESETPIN = resetBcmPinNumber
        self.DATAPIN = dataBcmPinNumber
        self.pigpiohost = pigpiohost
        self.pigpioport = pigpioport
        self.spichannel = spichannel
        self.spibaudrate = spibaudrate

        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpiod, is the daemon running? (sudo pigpiod)")
        self.piconnected = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """clean up stuff"""
        if self.piconnected:
            self.pi.stop()

    def _startTransmit(self):
        
        # prepare GPIO-Pins
        self.pi.set_mode(self.RESETPIN, gpio.OUTPUT)
        self.pi.set_mode(self.DATAPIN, gpio.OUTPUT)
        self.pi.set_pull_up_down(self.DATAPIN, gpio.PUD_OFF)
        self.pi.write(self.DATAPIN, 0)

        # reset transmitter before use
        self.pi.write(self.RESETPIN, 1)
        self.pi.write(self.RESETPIN, 0)
        sleep(.005)

        with Rfm69(host=self.pigpiohost, channel=self.spichannel, baudrate=self.spibaudrate, debug_level=0) as rf:
            # just to make sure SPI is working
            rx_data = rf.read_single(0x5A)
            if rx_data != 0x55:
                raise RuntimeError(f"Unexpected response reading SPI value, expected {0x55}, got {rx_data}.  Check RFM69 device is properly connected.")

            rf.write_single(0x01, 0b00000100)     # OpMode: STDBY

            #rf.write_burst(0x07, [0x6C, 0x9A, 0x00]) # Frf: Carrier Frequency 434.42MHz
            rf.write_burst(0x07, [0x6C, 0x4F, 0x5C]) # Frf: Carrier Frequency 433.42MHz/61.03515625 

            # Use PA_BOOST
            rf.write_single(0x13, 0x0F)
            rf.write_single(0x5A, 0x5D)
            rf.write_single(0x5C, 0x7C)
            rf.write_single(0x11, 0b01111111)     # Use PA_BOOST

            rf.write_single(0x18, 0b00000110)     # Lna: 50 Ohm, highest gain
            rf.write_single(0x19, 0b01000000)     # RxBw: 4% DCC, BW=250kHz

            # Transmit Mode
            rf.write_single(0x02, 0b01101000)     # DataModul: continuous w/o bit sync, OOK, no shaping
            rf.write_single(0x01, 0b00001100)     # OpMode: SequencerOn, TX

            timeout = 1
            timespent = 0
            # wait for ready
            while (rf.read_single(0x27) & 0x80) == 0 and timespent < timeout:
                timespent += 0.005
                sleep(.005)
                pass
                #print "waiting..."
            if timespent >= timeout:
                raise RuntimeError("Timed out waiting for ready signal after initialising RFM69")

    def _endTransmit(self):
        # reset transmitter
        self.pi.write(self.RESETPIN, 1)
        self.pi.write(self.RESETPIN, 0)
        sleep(.005)

    def sendWaveForm(self, waveform):
        
        self._startTransmit()

        # delete existing waveforms
        self.pi.wave_clear()
        self.pi.wave_add_new()

        self.pi.wave_add_generic(waveform)
        wid = self.pi.wave_create()
        self.pi.wave_send_once(wid)

        # wait until finished
        while self.pi.wave_tx_busy():
            sleep(0.1)

        self.pi.wave_clear()

        self._endTransmit()

    

    def sendCommand(self, address, command, rolling_code):
        
        wf = createWaveForm(self.DATAPIN, address, command, rolling_code, 3)

        self.sendWaveForm(wf)


COMMANDS={
        'null': 0x00,
        'up': 0x02,
        'down': 0x04,
        'stop': 0x01,
        'prog': 0x08,
        }

def main(buttoncode):
    """ main function """

    try:   
        # load current config
        with open("config.json") as f:

            config = json.load(f)
    except:
        config = {"rolling_code": 0, "address": "0xc30000"}

    rc = config["rolling_code"]

    # update config
    config["rolling_code"] += 1

    # write new config
    with open("config.json", "w") as f:
        json.dump(config, f)


    with SomfyRfm69Tx() as s69Tx:

        s69Tx.sendCommand(int(config["address"], 16), buttoncode, rc  )


if __name__ == "__main__":
    try:
        if sys.argv[1] in COMMANDS:
            main(COMMANDS[sys.argv[1]])
        else:
            print ("Unknown command:", sys.argv[1])
    except KeyboardInterrupt:
        print("KeyboardInterrupt")

    finally:
        #print "done"
        pass