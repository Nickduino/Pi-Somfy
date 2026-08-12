# Pi-Somfy

## 1 Overview

This project allows to operate multiple Somfy shutters using the **RTS protocol** from a Raspberry Pi with cheap hardware costing less than $2. It comes with a command line interface, a web interface and an Amazon Alexa interface. 

## 2 Hardware

This project has been developed and tested with a Raspberry Pi B+ and a Raspberry Pi 3 as the base platforms. Since the serial port and network are the only external ports used, the program could be used on other platforms with minor modifications and testing.

Wi-Fi connectivity and Ethernet cable should both work. Note that the hardware has to be reasonably close (i.e. in the same house or in the same aisle of your mansion: just like a physical remote) to the shutters you operate, as the signal strength will otherwise not be sufficient.

Pi-Somfy supports two RF hardware options:

1. A raw 433 MHz ASK/OOK transmitter module. This is the original low-cost hardware path.
1. An E07-M1101D-SMA CC1101 module. This is controlled over SPI and transmits the same Somfy RTS waveform through the CC1101 radio.

### Raw 433 MHz transmitter

For the original raw 433 MHz transmitter, you have to build your own hardware. Here are the steps to do so.

1. You need the RF Transmitter. If you wish to order it from eBay, this link may be helpful: <br/>[Order](https://www.ebay.com/sch/sis.html?_nkw=5x+433Mhz+RF+transmitter+and+receiver+kit+Module+Arduino+ARM+WL+MCU+Raspberry).<br/>Note that desoldering a 3 pin component isn't trivial, so ordering more than one may be a good idea in case of a screw up.
1. You need an oscillator for a 433.42 MHz frequency. The above RF transmitter comes with a common 433.93 MHz one, which will not work with your Somfy shutter. If you wish to order it from eBay, this link may be helpful: <br/>[Order](https://www.ebay.com/sch/sis.html?_nkw=433.42M+R433+F433+SAW+Resonator+Crystals+TO-39)
1. You will need cables to connect the transmitter to the Raspberry Pi. Any cable will do obviously, but I found these quite helpful. <br/>[Order](https://www.ebay.com/itm/40Pin-Multicolored-Dupont-Wire-Kits-Breadboard-Female-Jumper-Ribbon-Cable/113310899442)
1. OPTIONAL: If you intend to place your Raspberry Pi further than about 10 ft from your receiver (aka your shutter or awning), you may need an antenna. Literally any 17 cm solid core copper wire will do the job. But if you prefer to order a fancy full one, this one will come handy <br/>[Order](https://www.ebay.com/itm/10pcs-433MHz-antenna-Helical-antenna-Remote-Control-for-Arduino-Raspberry-pi/372691762881?hash=item56c628fec1:g:kf0AAOxyBPZTgvGe)

Once you have all the hardware handy, it's now time to swap the oscillator, which requires a bit of soldering. Reason for this is that the emitter you bought uses a common 433.93 MHz frequency, Somfy however requires a 433.__42__ MHz frequency. Take the following steps to exchange the oscillator
1. Identify the oscillator. It looks like this (marked with a red circle): <br/>![Front view](documentation/RF%20Transmitter%20front.jpg). <br/>Turn the RF Transmitter around. You will see that the oscillator is soldered in on 3 points <br/>![Back View](documentation/RF%20Transmitter%20back.jpg)
1. While pulling the oscillator from the front, heat up the 3 soldering point on the back with the soldering iron until the oscillator is detached from the board
1. Clean up the remaining solder mess on both desoldering braid or a desoldering pump
1. Now put in the new oscillator (make sure all 3 pins connect through the print) and solder it in again
1. Solder an antenna to the ANT pad. The ideal is a 17 cm solid core wire but almost anything will do the job. I used this antenna from ebay ([Order](https://www.ebay.com/itm/10pcs-433MHz-antenna-Helical-antenna-Remote-Control-for-Arduino-Raspberry-pi/372691762881?hash=item56c628fec1:g:kf0AAOxyBPZTgvGe)) as I like the outlook. If your Pi is less than 10 ft from the receiver, it may work without antenna.

And you are done on the mods!

Now the last step is to connect your adjusted RF transmitter to your Raspberry Pi. Use the following diagram to help you connect it 

![Diagram](documentation/Wiring%20Diagram.png)

Note that I used GPIO 4 but you can change the value of __TXGPIO__ to whatever you want if you choose a different way to connect your RF emitter. This is a configuration parameter in operateShutters.conf.

OK. now this all should look like this. Note that some of the pictures are a bit confusing with regards to which GPIO a cable connects to. It's easier to see on the above diagram. But if you struggle, maybe the [Wiring Diagram](documentation/Wiring%20Diagram.txt) helps.

Set the top-level RF backend in `operateShutters.conf`:

```ini
TXGPIO = 4
RFBackend = raw_433
```

Raw 433 MHz transmitter connection photos:

![Full Picture](documentation/Full%20Assembly.jpg)<br/>
![Pi Connection](documentation/Connection.jpg)<br/>
![RF Transmitter Connection](documentation/Sender.jpg)<br/>

### 2.1 Receiver (optional) — tracking physical remotes

Everything above (§2) covers *sending* commands, and is all you need to
operate your shutters from Pi-Somfy. This section adds an optional extra:
*listening* for presses on your existing physical Somfy remotes, so
pressing one updates Pi-Somfy's tracked shutter position (and Home
Assistant, via MQTT or the custom component) immediately — not just
commands issued through the app itself.

**This is purely additive — it doesn't replace or change anything above.**
Your existing RF transmitter (with its oscillator swap) stays exactly as
it is; the receiver is a second, independent piece of hardware you add
alongside it. And unlike the transmitter, **the receiver needs no
soldering at all**: CC1101 modules are sold as ready-made breakout boards
with header pins, so it's just a few jumper wires straight into the Pi's
GPIO header.

#### What to buy

Any CC1101 breakout module works, as long as you can match its pins to
the table below. This is the exact module used to build and test this
feature: [CC1101 433 MHz module (AliExpress)](https://he.aliexpress.com/item/1005005933919297.html).
You'll also want a handful of female-to-female jumper wires to connect it
to the Pi (the same kind used for the transmitter in §2).

#### Wiring

Match module pins by silkscreen **label**, not position — layouts vary
between sellers, and MOSI/MISO are sometimes printed as `SI`/`SO` instead:

| CC1101 pin | Signal | Default GPIO | Physical pin (Pi 4) |
|---|---|---|---|
| VCC | 3.3 V supply | — | 17 (or 1) — **never 5 V** |
| GND | ground | — | 39 |
| SCK | SPI clock | GPIO 21 | 40 |
| MOSI (SI) | SPI data → radio | GPIO 20 | 38 |
| MISO (SO) | SPI data → Pi | GPIO 19 | 35 |
| CSN | chip select | GPIO 16 | 36 |
| GDO0 | demodulated data out | GPIO 26 | 37 |
| GDO2 | — | not connected | — |
| ANT | antenna | — | 17 cm solid-core wire, **required** |

![Raspberry Pi 4 GPIO wiring for the RF transmitter and CC1101 receiver](documentation/CC1101%20Wiring%20Diagram.svg)

*(Shown together for a complete GPIO reference — the transmitter wiring above is the same setup from §2, unchanged.)*

#### Step-by-step setup

1. Buy a CC1101 module (see above) and some jumper wires.
2. **Power off the Pi**, then wire the module's 6 pins per the table above.
3. **Enable SPI on the Pi itself**, even though it's bit-banged over
   ordinary GPIOs rather than the Pi's dedicated hardware SPI peripheral —
   in practice (confirmed on Home Assistant OS) the receiver still needs
   the `spi` device-tree overlay active, or it won't work:
   - Power down the Pi, remove the Micro-SD card, and read it on another
     computer (it mounts as a normal FAT32 drive, `boot`/`bootfs`).
   - Open `config.txt` in a text editor, add `dtparam=spi=on` at the
     bottom, and save.
   - Reinsert the SD card into the Pi and power it back on.
4. Enable it in config: set `RXGPIO = 26` in `operateShutters.conf`'s
   `[General]` section (and `RXSpiSCK`/`RXSpiMOSI`/`RXSpiMISO`/`RXSpiCSN`
   too, only if you wired it to different pins than the table above).
   Running the Home Assistant add-on instead? The same options are on its
   configuration page as `rx_gpio_pin`/`spi_sck`/`spi_mosi`/`spi_miso`/`spi_csn`
   — no manual config file editing needed.
5. Restart Pi-Somfy (or the add-on).
6. Pair a physical remote to a shutter from the web UI's "Physical
   Remotes" section (see §5 below): press a button on the remote, find it
   listed under "Recently Heard", and assign it to one or more shutters.

Leave `RXGPIO` unset/commented out (or `rx_gpio_pin` blank in the add-on)
to run without a receiver at all, exactly as before this feature existed.

### 2.2 CC1101 as transmitter (optional) — E07-M1101D-SMA module

Pi-Somfy can also drive an E07-M1101D-SMA CC1101 module as the **transmitter**, replacing the raw 433 MHz GPIO path. This module is controlled over SPI and uses the CC1101 asynchronous transmit mode, with the Somfy RTS waveform driven into GDO0.

The E07-M1101D-SMA must be powered from 3.3V. Do not connect VCC or any logic pin to 5V.

| E07-M1101D-SMA pin | Raspberry Pi 4 physical pin | Raspberry Pi signal |
| --- | ---: | --- |
| 1 GND | 6 | GND |
| 2 VCC | 1 or 17 | 3.3V |
| 3 GDO0 | 7 | GPIO4 / TXGPIO |
| 4 CSN | 24 | SPI0 CE0 / GPIO8 |
| 5 SCK | 23 | SPI0 SCLK / GPIO11 |
| 6 MOSI | 19 | SPI0 MOSI / GPIO10 |
| 7 MISO/GDO1 | 21 | SPI0 MISO / GPIO9 |
| 8 GDO2 | 22 | GPIO25, optional |

Enable SPI on the Pi, then set the top-level RF backend in `operateShutters.conf`:

```ini
TXGPIO = 4
SendRepeat = 5
RFBackend = cc1101
CC1101Frequency = 433.42
CC1101SPIBus = 0
CC1101SPIDevice = 0
CC1101OutputPower = 0xC6
CC1101TransmitSettleSeconds = 0.05
```

`CC1101TransmitSettleSeconds` keeps GDO0 low briefly after the CC1101 enters asynchronous TX mode before the Somfy waveform starts. `0.05` has worked reliably with an E07-M1101D-SMA on a Raspberry Pi 4. If one shade still misses commands, increase `SendRepeat` first because it sends more copies of the same Somfy frame.

## 3 Software

If you are new to using a Raspberry Pi and Linux please refer to other sources for coming up to speed with the environment. Having a base knowledge will go a long way. This [site](https://www.raspberrypi.org/help/) is a great place to start if you are new to these topics.

If you are not familiar with remote login commands for Linux/Unix, two useful commands if you are not using a GUI on your raspberry pi are "ssh" and "scp". These commands allow you to run your Pi without a monitor or user interface. These programs allow you to remotely login to your Pi and remotely transfer files to your Pi. This [page](https://linuxacademy.com/blog/linux/ssh-and-scp-howto-tips-tricks/) describes both programs. You can also do a web search on these programs to find other resources on their use. In short you need to have at minimum a basic understanding of using a command line, preferably some experience with Linux and the ability to transfer files to a Raspberry Pi and execute them.

The Raspberry Pi organization has documentation on installing an operating system on your Raspberry Pi. It is located [here](https://www.raspberrypi.org/documentation/installation/installing-images/README.md).

Once the Pi has its basic setup (an operating system and an internet connection) working, ssh into your Raspberry Pi. The examples below install into `~/Pi-Somfy`; if you use a different directory, run the commands from that checkout.

The next step is to download the Pi-Somfy project files to your Raspberry Pi. The easiest way to do this is to use the "git" program. Most Raspberry Pi distributions include the git program (except Debian Lite).

Whether or not it is already installed, it's good practice to type the following:

```sh
sudo apt-get update
sudo apt-get install git
```
(If git isn't installed, it will install it; if it was previously, it will update it)

Once git is installed on your system, clone the project:

```sh
cd ~
git clone https://github.com/Nickduino/Pi-Somfy.git
cd Pi-Somfy
```

The above command will make a directory named `Pi-Somfy` and put the project files in this directory.

Next, install the Raspberry Pi OS packages used by Pi-Somfy. On current Raspberry Pi OS releases, the GPIO package is `python3-pigpio`; the bare `pigpio` package name may not be installable.

```sh
sudo apt-get update
sudo apt-get install python3-venv python3-pip python3-pigpio python3-lgpio python3-spidev
```

For the E07-M1101D-SMA / CC1101 backend, enable SPI:

```sh
sudo raspi-config nonint do_spi 0
ls -l /dev/spidev*
```

If `/dev/spidev0.0` and `/dev/spidev0.1` do not appear, reboot and check again.

Create a Python virtual environment that can see the Raspberry Pi OS GPIO/SPI packages, then install the Python requirements:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt
```

The `--system-site-packages` option is intentional: Raspberry Pi OS supplies `pigpio`, `lgpio`, and `spidev` as apt packages, while `requirements.txt` installs or verifies the Python packages used by the app, including `cc1101`.

If this is a new install, create the config from the default and choose the RF backend:

```sh
cp defaultConfig.conf operateShutters.conf
```

For the raw 433 MHz transmitter, keep:

```ini
RFBackend = raw_433
```

For the E07-M1101D-SMA / CC1101 module, set:

```ini
SendRepeat = 5
RFBackend = cc1101
CC1101Frequency = 433.42
CC1101OutputPower = 0xC6
CC1101TransmitSettleSeconds = 0.05
```

Next, test the Python environment by typing:

```sh
.venv/bin/python operateShutters.py -h
```

You should see the help text explaining the [Command Line Interface](documentation/p4.png)

## 4 Usage

Note that the config file won't exist the first time you run the application unless you copied it from `defaultConfig.conf` during install. In that case, a new config file will be created based on the name you specified (e.g. `operateShutters.conf` in your checkout). Once it has been created, you can modify it to change your need (SSL or not, which port is used, etc.), it will not be erased with an update. If you messed up something, just delete it and relaunch operateShutters.py, a new vanilla copy will be generated.

You have 6 ways to operate. The recommended operation mode is mode 5. But the other 5 modes are explained here for completeness:

1. Command line Interface<br/>You can use either of the following commands to operate a shutter called<br/>

**Arguments:**

    shutterName                             Name of the shutter
    -h, --help                              Show this help message and exit
    -c CONFIGFILE, --config CONFIGFILE      Name of the config File (incl full Path)
    -up, -u                                 Raise the shutter
    -down, -d                               lower the shutter
    -stop, -s                               Stop the shutter
    -program, -p                            Send a program signal
    -press BTN [BTN...]                     Simulate a chord press of a the specified remote buttons
                                            ('up', 'down', 'stop'/'my', and 'program')
    -long                                   When used with the -press option, simulates a long press
    -demo                                   Lower the shutter, wait, then raise it again
    -duskdawn DUSKDAWN DUSKDAWN, -dd DUSKDAWN DUSKDAWN
                                            Automatically lower the shutter at sunset and raise the
                                            shutter at sunrise, provide the evening delay and
                                            morning delay in minutes each
    -auto, -a                               Run schedule based on config. Also will start up the web-server 
                                            which can be used to setup the schedule.
    -echo, -e                               Enable Amazon Alexa (Echo) integration
    -mqtt, -m                               Enable MQTT integration



**Examples:**
All three command the shutter named corridor. The first one will raise it. The second one will lower it. The third one will lower the shutter at sunset and raise it again 60 minutes after sunrise.
```sh
.venv/bin/python operateShutters.py corridor -c operateShutters.conf -u
.venv/bin/python operateShutters.py corridor -c operateShutters.conf -d
.venv/bin/python operateShutters.py corridor -c operateShutters.conf -dd 0 60
``` 

2. Manually start Web interface only<br/>You can start the web-interface by typing:<br/>Once started, you can access the web interface at http://IPaddressOfYourPi:80. From there you can further modify your settings.   
```sh
sudo .venv/bin/python operateShutters.py -c operateShutters.conf -a 
```    

3. Manually start Web interface and Alexa interface<br/>You can start the web-interface by typing:
```sh
sudo .venv/bin/python operateShutters.py -c operateShutters.conf -a -e
```    

4. Manually start Web interface and MQTT integration (for Home Assistant)<br/>You can start the web-interface by typing:
```sh
sudo .venv/bin/python operateShutters.py -c operateShutters.conf -a -m
```    

5. Finally, the recommended way to operate it is using a systemd service on boot time. You can do so by typing:
```sh
sudo bash ./installService.sh
```
The service will be installed as `pi-somfy.service` and starts after network connectivity.
By default, the service runs the web interface with `-a`. To also enable MQTT and Alexa, install it like this:

```sh
PI_SOMFY_ARGS="-a -m -e" sudo -E bash ./installService.sh
```

If you want to stop the service simply type:
```sh
sudo systemctl stop pi-somfy.service
```  
If you want to start the service simply type:
```sh
sudo systemctl start pi-somfy.service
```  
If you want to restart the service simply type:
```sh
sudo systemctl restart pi-somfy.service
```  
The installer writes the service file with the path to your current checkout and uses `.venv/bin/python` when that virtual environment exists.
```
ExecStart=/path/to/Pi-Somfy/.venv/bin/python /path/to/Pi-Somfy/operateShutters.py -c /path/to/Pi-Somfy/operateShutters.conf -a
```

6. Alternatively, you can use cron to run the program at boot time. You can do so by typing:
```sh
sudo crontab -e 
```
Note, that "crontab -e" will just open a console-based text editor that you can edit the crontab script. The first time you run "crontab -e" you will be prompted to choose the editor. I recommend nano. From the crontab window, add the following to the bottom of the crontab script

```
@reboot sleep 60; cd /path/to/Pi-Somfy && .venv/bin/python operateShutters.py -c operateShutters.conf -a -e -m
0 * * * * cd /path/to/Pi-Somfy && .venv/bin/python operateShutters.py -c operateShutters.conf -a -e -m
```

And save the crontab schedule. (if using nano type press ctrl-o to save the file, ctrl-x to exit nano). Now, every time your system is booted operateShutters will start.

The program is not known to crash. Hence restarting it every hour is not really required. But it does not hurt either. So up to you if you wish to use both of the above lines or just the first one. In any case, you will need to restart your Raspberry Pi once you have completed step 4. To do so, type "sudo reboot". 

To stop the program from running in the background, type:

```sh
sudo pkill -f operateShutters.py
```

## 5 Web GUI

Using your web-browser, navigate to: http://IPaddressOfYourPi:80

First time you use the Web GUI, it's important that you follow these 3 steps:

1. Set up your location. This is required to correctly determine the time of sunrise and sunset. To do so, navigate to the top menu item "Settings". Use the map to pinpoint your location. You can also use the search functionality on the left-hand side (magnifier icon) and type your address. Press "Save"

1. You will need to set up your shutters and program your remote control. To do so, select the second menu item "Add/Remove Shutters". <br/>![Screenshot](documentation/p1.png)<br/>
Click the "Add" button, select the name for your shutter (this is also the name that the Amazon Alexa app will use later) and click on the "save" icon. Then follow the on-screen instructions for programming your shutter. For installing shutters from the factory default configuration, use the Configure button.

1. Next, make sure your shutters work. The easiest way to verify is to use the "Manual Operations" menu. <br/>![Screenshot](documentation/p2.png)<br/> You can raise and lower your shutters by clicking on the relevant icons.

1. Finally, it's time to program your shutters schedule. To do so, use the "Scheduled Operations" menu. <br/>![Screenshot](documentation/p3.png)<br/>

1. If you've wired up the optional CC1101 receiver (§2.1), pair your physical remotes using the "Physical Remotes" menu. Press a button on the remote, find it listed under "Recently Heard", click the assign icon, and pick which shutter(s) it should control.

1. If you set up the CC1101 receiver, also set each shutter's "My" position — essential so Pi-Somfy's tracked position stays correct when a physical remote's STOP/MY button sends the shutter there. In "Add/Remove Shutters", click the Configure (wrench) icon, open "Setting the 'My' Position", and enter the matching percentage (a warning shows on Manual Operation until you do). To find the right number: send the shutter to 0% first (the one position Pi-Somfy tracks exactly), then use the wizard's own up/down buttons — not the remote — to reach the physical My position, and copy the percentage shown on Manual Operation into the Save field. <br/>![Screenshot](documentation/p5.png)<br/>


## 6 Alexa Integration

Before you can use the Amazon Alexa integration, you need to make sure you set up all shutters, by using "Add/Remove Shutters" in the Web GUI.

New or removed shutters are automatically picked up by the Alexa integration within a few seconds — no restart is required. However, you will still need to ask Alexa to discover devices before she can control them.

So once all your shutters are set up and testing on the Web GUI, go to your Echo speaker and ask Alexa to discover your device. Say, "Discover my devices," or select Add Device in the Devices section of the Alexa app.

Once Alexa has discovered your shutters, you can use the Alexa app to complete the setup. 

To lower your shutter via the Echo speaker, say "Alexa, turn on {SHUTTERNAME}". And to raise the shutter again, say “Alexa, turn off {SHUTTERNAME}".

If you prefer to state the likes of "Alexa, OPEN the shutter" or "Alexa, CLOSE the shutter" (rather than using the words ON or OFF), you can set up a Routine with Alexa.

## 7 Home Assistant Integration (Recommended)

Pi-Somfy can integrate directly with [Home Assistant](https://www.home-assistant.io/) using a **custom component** and an optional **Supervisor add-on**. This is the recommended approach — it communicates directly with the Pi-Somfy web API, so **no MQTT broker is needed**.

### Which do you need?

| Your Setup | What to install |
|---|---|
| RF transmitter attached to a **separate Pi** on the network | Custom Component only |
| RF transmitter attached to the **same Pi running Home Assistant** | Custom Component **and** Add-on |

- The **Custom Component** adds Pi-Somfy as a native HA integration with cover entities, position control, and automatic discovery.
- The **Add-on** runs the Pi-Somfy backend (web server + GPIO control) as a Supervisor add-on, so you don't need a separate Pi.

### Installing the Custom Component

#### Option A: HACS (recommended)

1. In Home Assistant, go to **HACS → Integrations**.
2. Click the three-dot menu (top right) and select **Custom repositories**.
3. Add `https://github.com/Nickduino/Pi-Somfy` with category **Integration** and click **Add**.
4. Search for "Pi-Somfy" in HACS, click **Download**, and restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration**, search for "Pi-Somfy", and enter the IP address and port of your Pi-Somfy instance (default port: 80).

#### Option B: Manual install

1. Copy the `custom_components/pi_somfy` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for "Pi-Somfy", and enter the IP address and port of your Pi-Somfy instance (default port: 80).

### Installing the Add-on

#### Option A: Add-on repository (recommended)

1. Go to **Settings → Add-ons → Add-on Store**, click the three-dot menu (top right) and select **Repositories**.
2. Add `https://github.com/Nickduino/Pi-Somfy` and click **Add**.
3. Find "Pi-Somfy" under the new repository and install it.

#### Option B: Manual install

1. Copy the `somfy-ha-addon` folder to your Home Assistant `addons/somfy-ha-addon` directory.
2. Go to **Settings → Add-ons → Add-on Store** and click the refresh button.
3. Find "Pi-Somfy" under "Local add-ons" and install it.
4. Configure the GPIO pin in the add-on settings (default: GPIO 4).
5. Start the add-on, then install the Custom Component (above) pointing to `localhost` or `homeassistant.local`.

### Raspberry Pi 5 Support (Experimental)

Pi 5 uses a different GPIO chip (RP1) which is incompatible with the pigpio library used on older Pis. Pi-Somfy includes **experimental** support for Pi 5 using the lgpio library, with automatic hardware detection. However, **we have not been able to fully test this ourselves**. If you are running on a Pi 5 and can help validate, your feedback would be greatly appreciated — please open an issue on GitHub.

## 8 MQTT Integration

> **Note:** If you are using Home Assistant, the custom component in Section 7 communicates directly with the Pi-Somfy web API and does not require an MQTT broker. The MQTT integration is still fully supported and works well, especially if you already have an MQTT broker or want to integrate with other home automation systems.

While the MQTT integration was written specifically for [Home Assistant](https://www.home-assistant.io/), nothing is stopping the use of this integration for other purpose. But more on this later

First, to use this integration, make sure you configure your `operateShutters.conf` with the right parameters. Look out for the following lines:

```
MQTT_Server = 192.168.1.x
MQTT_Port = 1883
MQTT_User = xxxxxxx
MQTT_Password = xxxxxxx
```
and make sure they match the setup of your MQTT Broker. If you are using Home Assistant, you can conveniently use the "Mosquitto broker" add-on inside Home Assistant. For more information refer to the relevant [Documentation](https://github.com/home-assistant/hassio-addons/tree/master/mosquitto)

If you choose not to use the Home Assistant add-in, you can download the [Mosquitto Broker](https://mosquitto.org/) and refer to the [Broker configuration](https://mosquitto.org/man/mosquitto-8.html)

Second, start `operateShutters.py` with the "-m" option. This should look similar to this:

```sh
.venv/bin/python operateShutters.py -c operateShutters.conf -a -m
```

And that's it, you are all set. 

So if you use Home Assistant, you have 2 options:

### a.) you use Home Assistant's [MQTT Discovery functionality](https://www.home-assistant.io/docs/mqtt/discovery/). 

To do so, add the following line to `operateShutters.conf`

```
EnableDiscovery = true
```

and also add the following line to your `configuration.yaml` in Home Assistant:

```
mqtt:
  discovery: true
```
   
Note that both Pi-Somfy & Home Assistant need to be restarted before this will work. Home Assistant will henceforth auto discover any new  shutters you add

### b.) Don't use Home Assistants MQTT Discovery functionality.

If so, no further changes are required to `operateShutters.conf`. However you will have to add the following lines to `configuration.yaml` in Home Assistant for every shutter you have (replace 0x2670xx with the shutters actual RTS_Address, which you can get from your `operateShutters.conf` file): 

```
cover:
   - platform: mqtt
     name: '{SHUTTERNAME}'
     payload_open: 100
     payload_close: 0
     command_topic: 'somfy/0x2670xx/level/cmd'
     position_topic: 'somfy/0x2670xx/level/set_state'
     set_position_topic: 'somfy/0x2670xx/level/cmd'
     state_open: 100
     state_closed: 0
```

And that's it! 

Finally, in case of any difficulties with this integration, 2 more useful commands:

### a.) See messages on the MQTT Broker
If you want to see what messages are passed on the MQTT Broker, you can use the following to listen to all messages (assuming you set up mosquitto with a username and password):

```
mosquitto_sub -h 192.168.x.x -p 1883 -u [username] -P [password] -t '#' -v
```

### b.) Send messages to the MQTT Broker, for Pi-Somfy to pick up
If you want to post a message to the MQTT Broker for your Pi-Somfy to pick up, you can use following to send messages (assuming you set up mosquitto with a username and password):

```
mosquitto_pub -h 192.168.x.x -p 1883 -u [username] -P [password] -t 'somfy/0x2670xx/level/cmd' -m '0'
mosquitto_pub -h 192.168.x.x -p 1883 -u [username] -P [password] -t 'somfy/0x2670xx/level/cmd' -m '100'
```

Those 2 commands will lower and raise your shutters.

## 9 Modernization (2025–2026)

The project has been updated to use current software libraries and fix a number of issues.

### Upgrading from a previous version

If you already have Pi-Somfy installed, follow these steps to upgrade:

```sh
cd ~/Pi-Somfy
git pull
.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart pi-somfy.service
```

Note: if you are not using MQTT (`-m` flag), `paho-mqtt` is no longer required and you can skip installing it. Your existing `operateShutters.conf` will be preserved — the upgrade only replaces code files.

### What changed

### Web Interface
- **Modernized design**: The web interface has been fully updated for a modern look and feel, with a mobile-friendly layout that works well on phones and tablets.
- **Cleaner icons**: All button icons are now crisp vector graphics instead of the old bitmap images.
- **Schedule page fixes**: Fixed several visual glitches — toggle labels, clock picker popup, and dropdown menus now display correctly in all situations. Also fixed a bug where deleting a schedule and then adding a new one could fail.

### Backend
- **Home Assistant custom component**: New native HA integration with cover entities, position tracking, and automatic shutter discovery.
- **Home Assistant Supervisor add-on**: Run Pi-Somfy directly on your HA system — no separate Pi required.
- **Pi 5 support (experimental)**: Automatic detection of Pi 5 hardware with lgpio-based GPIO control as an alternative to pigpio.
- **paho-mqtt is now optional**: The MQTT library is only imported when you use the `-m` flag, so it no longer needs to be installed if you don't use MQTT.
- **Alexa: no restart needed**: When you add or remove a shutter via the web interface, the Alexa integration picks it up automatically — you no longer need to restart the service.
- **Alexa: more reliable discovery**: Alexa should now discover all your shutters more reliably. Discovery responses are sent multiple times to avoid missed devices.
- **Home Assistant (MQTT)**: Updated to the latest Home Assistant MQTT discovery format. Also now works with both older and newer versions of the MQTT library.
- **Config file safety**: The configuration file is now written more carefully to avoid corruption if the system loses power or crashes mid-write.
- **Bug fixes**: Fixed several bugs in the scheduler (events not firing correctly in certain conditions), the configuration reader (occasional wrong error messages), and shutter control (demo mode not working properly).
- **Code cleanup**: Consolidated 9 Python files into 6, removed unused code, and updated deprecated function calls for compatibility with current versions of Python.
- **Windows**: The application can now run on Windows for development and testing purposes (Alexa and web interface work; GPIO obviously requires a Raspberry Pi).

## 10 Credits
This Library was ported from [Arduino sketch](https://github.com/Nickduino/Somfy_Remote) onto the Pi by @Nickduino to open and close his blinds automatically. 

If you want to learn more about the Somfy RTS protocol, check out [Pushtack](https://pushstack.wordpress.com/somfy-rts-protocol/). 

### Community Contributions
The following fixes were contributed by the community and incorporated into this release:
- **paho-mqtt 2.x compatibility** — Based on issue identified by @digitalgravy ([PR #164](https://github.com/Nickduino/Pi-Somfy/pull/164)). Instead of pinning to <2.0.0, the code now supports both paho-mqtt 1.x and 2.x.
- **Shutter ID case-mangling fix** — Based on fix by @gbsallery ([PR #156](https://github.com/Nickduino/Pi-Somfy/pull/156)) and analysis by @malys ([PR #159](https://github.com/Nickduino/Pi-Somfy/pull/159)). Shutter IDs containing hex letters (a-f) are now consistently uppercased when writing rolling codes, preventing duplicate config entries.


## 11 License
![Image of the license](https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png)

[Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
