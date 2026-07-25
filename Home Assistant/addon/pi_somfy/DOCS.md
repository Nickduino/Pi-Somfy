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

| Option        | Default | Description                                                              |
|---------------|---------|---------------------------------------------------------------------------|
| `gpio_pin`    | `4`     | GPIO pin number for the 433.42 MHz transmitter                          |
| `rx_gpio_pin` | (none)  | GPIO wired to a CC1101 receiver's data output. Leave blank to disable the physical-remote receiver entirely. |
| `spi_sck`     | `21`    | CC1101 bit-banged SPI clock GPIO (only used when `rx_gpio_pin` is set)   |
| `spi_mosi`    | `20`    | CC1101 bit-banged SPI MOSI GPIO (only used when `rx_gpio_pin` is set)    |
| `spi_miso`    | `19`    | CC1101 bit-banged SPI MISO GPIO (only used when `rx_gpio_pin` is set)    |
| `spi_csn`     | `16`    | CC1101 bit-banged SPI chip-select GPIO (only used when `rx_gpio_pin` is set) |

### Physical remote receiver (optional)

Setting `rx_gpio_pin` enables listening for physical Somfy RTS remote button
presses via a CC1101 receiver module, so a physical remote and the app stay
in sync. Pairing a physical remote to a shutter is not yet exposed in the
web UI — add it manually to
`[PhysicalRemotes]` in `/data/operateShutters.conf` (map the remote's
address to a comma-separated list of shutterId(s), same format as the
`[Shutters]` section).

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

- This add-on runs Pi-Somfy with the web interface and scheduler only (no MQTT, no Alexa emulation)
- For MQTT or Alexa integration, run Pi-Somfy standalone on a dedicated Raspberry Pi
- Shutter position tracking is estimated based on timing and is reset on restart

## Support

For issues, visit the [Pi-Somfy GitHub repository](https://github.com/Nickduino/Pi-Somfy/issues).
