# Pi-Somfy

#1 Overview

This project allowes to operate multiple Somfy Shutter with a Rasberry Pi with cheap hardware costing less than $2. It comes with a command line interface, a web interface and an Amazon Alexa interface. 

#2 Hardware

This project has been developed and tested with a Raspberry Pi 3 as the base platform. Since the serial port and network are the only external ports used, the program could be used on other platforms with minor modifications and testing.

In development and testing I used the Raspberry Pi3 both with WiFI connectivity and Ethernet cable. Note that the hardware has to be reasonable close to the shutters you operate, as the signal strength will otherwise not be sufficient.

As of now, you have to build your own hardware. Here are the steps to do so.
1. You need the RF Transmitter. If you wish to order it from ebay, this link maybe helpful: [Order](https://www.ebay.com/sch/sis.html?_nkw=5x+433Mhz+RF+transmitter+and+receiver+kit+Module+Arduino+ARM+WL+MCU+Raspberry). Note that I briked my first Transmitter when soldering, so ordering more than one may be a good idea.
1. You need an oscillator for a 433.42 MHz frequency. The above RF transmitter comes with a common 433.93 MHz one, which will not work with your Somfy shutter. If you wish to order it from ebay, this link maybe helpful: [Order](https://www.ebay.com/sch/sis.html?_nkw=433.42M+R433+F433+SAW+Resonator+Crystals+TO-39)
1. You will need cables to connect the transmitter to the Raspberry Pi. Any cable will do obviosuly, but I found these quite helpful [Order](https://www.ebay.com/itm/40Pin-Multicolored-Dupont-Wire-Kits-Breadboard-Female-Jumper-Ribbon-Cable/113310899442)

Once you have all the hardware, you will need to 

#4 Credits
This Library was ported from [Arduino sketch](https://github.com/Nickduino/Somfy_Remote) onto the Pi by @Nickduino to open and close my blinds automatically. 

If you want to learn more about the Somfy RTS protocol, check out [Pushtack](https://pushstack.wordpress.com/somfy-rts-protocol/). It's because of this blog that I was able to write all my code.


It's a script to open and close your Somfy (and SIMU) blinds using the RTS (or Hz) protocol with a Raspberry Pi and a cheap RF emitter. Your emitter has to use the 433.__42__ MHz frequency; the simplest might be to choose a common 433.93 MHz one and to swap its oscillator for a 433.42 MHz one bought separetely.
Then, connect it to your Raspberry Pi (I used GPIO 4 but you can change the value of __TXGPIO__ to whatever you want).

The script will use the __ephem library__ and __pigpiod daemon__ to open and close Somfy (or SIMU) blinds, depending on the time of sunrise/sunset (or whatever you feel like: open your blinds the first monday of the month if you want).
The remote address (which you'll create and will be recognised by your blinds as a new remote) and rolling code (incremented every time you send a frame) are stored in a specific file for each remote (one per blind, one per room, one per level, ...).
