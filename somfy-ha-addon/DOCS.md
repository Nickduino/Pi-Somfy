# Pi-Somfy Home Assistant Add-on

## Overview

This add-on runs [Pi-Somfy](https://github.com/Nickduino/Pi-Somfy) directly on your Home Assistant host, allowing you to control Somfy RTS shutters via 433.42 MHz RF using the Raspberry Pi's GPIO pins.

## Prerequisites

- A Raspberry Pi running Home Assistant OS
- A 433.42 MHz RF transmitter connected to a GPIO pin (default: GPIO 4)
- See the [Pi-Somfy wiring diagram](https://github.com/Nickduino/Pi-Somfy) for hardware setup

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the **Pi-Somfy** add-on
3. Configure the GPIO pin if different from the default (4)
4. Start the add-on

## Configuration

| Option           | Default                | Description                                                              |
|------------------|-------------------------|---------------------------------------------------------------------------|
| `gpio_pin`       | `4`                     | GPIO pin number for the 433.42 MHz transmitter                          |
| `rx_gpio_pin`    | (none)                  | GPIO wired to a CC1101 receiver's data output. Leave blank to disable the physical-remote receiver entirely. |
| `spi_sck`        | `21`                    | CC1101 bit-banged SPI clock GPIO (only used when `rx_gpio_pin` is set)   |
| `spi_mosi`       | `20`                    | CC1101 bit-banged SPI MOSI GPIO (only used when `rx_gpio_pin` is set)    |
| `spi_miso`       | `19`                    | CC1101 bit-banged SPI MISO GPIO (only used when `rx_gpio_pin` is set)    |
| `spi_csn`        | `16`                    | CC1101 bit-banged SPI chip-select GPIO (only used when `rx_gpio_pin` is set) |
| `enable_mqtt`    | `false`                 | Enable the MQTT bridge, using the broker connected via the Supervisor (e.g. the Mosquitto add-on) |

### Physical remote receiver (optional)

Setting `rx_gpio_pin` enables listening for physical Somfy RTS remote button
presses via a CC1101 receiver module, so a physical remote and the app stay
in sync. Pair a physical remote to a shutter from the web UI's "Physical
Remotes" section: press a button on the remote, find it listed under
"Recently Heard", and assign it to one or more shutters.

**Before enabling `rx_gpio_pin`, SPI must be enabled on the host**, even
though the receiver bit-bangs SPI over ordinary GPIOs rather than using
the Pi's dedicated hardware SPI peripheral — confirmed necessary in
practice on Home Assistant OS. Power down the Pi, read the Micro-SD card
on another computer (it mounts as a normal FAT32 `boot`/`bootfs` drive),
add `dtparam=spi=on` to the bottom of `config.txt`, then reinsert the card
and power the Pi back on.

### MQTT (optional)

Setting `enable_mqtt` enables the MQTT bridge alongside the web UI, publishing
Home Assistant MQTT auto-discovery for every shutter (cover entities with
live position and open/closing state) to whichever broker is connected via
the Supervisor — install and start the official Mosquitto broker add-on and
Pi-Somfy will find it automatically, no broker details to enter. Useful if
you want push-based updates instead of the custom integration's REST polling.
Leave `enable_mqtt` off to run without MQTT, exactly as before.

If your broker is not running as a Home Assistant add-on, this toggle will not
find it. Run Pi-Somfy standalone with `-m` and set the broker details in
`operateShutters.conf` instead.

## Web UI

The add-on provides a web interface accessible in two ways:

- **Sidebar**: Click "Pi-Somfy" in the Home Assistant sidebar (uses ingress)
- **External**: Open `http://<your-ha-ip>:9909` in any browser (uses port mapping)

Use the web UI to:
- Add and configure shutters
- Pair remotes using the programming feature
- Manually control shutters
- Set up the geographic location (for sunrise/sunset scheduling)

## Integration with Home Assistant

When this add-on is running, the **Pi-Somfy** custom integration can automatically discover it. Install the Pi-Somfy integration via HACS, and it will offer to set itself up using the local add-on.

If the integration is already installed, go to **Settings > Devices & Services > Add Integration > Pi-Somfy** and it should auto-detect the add-on.

## Data Persistence

Shutter configuration and rolling codes are stored in `/data/operateShutters.conf` and persist across add-on updates and restarts.

## Notes

- This add-on runs Pi-Somfy with the web interface, scheduler, and (if `enable_mqtt` is set) MQTT — no Alexa emulation
- For Alexa integration, run Pi-Somfy standalone on a dedicated Raspberry Pi
- Shutter position is estimated based on movement timing, but persists across restarts (saved to `/data/operateShutters.conf`'s `[ShutterPositions]` section as it changes)

## Support

For issues, visit the [Pi-Somfy GitHub repository](https://github.com/Nickduino/Pi-Somfy/issues).
