#!/usr/bin/with-contenv bashio

# Read configuration from add-on options
GPIO_PIN=$(bashio::config 'gpio_pin')

bashio::log.info "Pi-Somfy Add-on starting..."
bashio::log.info "GPIO pin: ${GPIO_PIN}"

# Ensure the persistent config directory exists
CONFIG_FILE="/data/operateShutters.conf"
if [ ! -f "${CONFIG_FILE}" ]; then
    bashio::log.info "No existing config found, creating from defaults..."
    cp /somfy/defaultConfig.conf "${CONFIG_FILE}"
fi

# Update the TXGPIO setting in the config file
if grep -q "^TXGPIO" "${CONFIG_FILE}"; then
    sed -i "s/^TXGPIO.*/TXGPIO = ${GPIO_PIN}/" "${CONFIG_FILE}"
else
    sed -i "/^\[General\]/a TXGPIO = ${GPIO_PIN}" "${CONFIG_FILE}"
fi

# RX receiver (physical Somfy remotes) is optional — only write RXGPIO/RXSpi*
# into the config file if the user set rx_gpio_pin, so operateShutters.py's
# `config.RXGPIO is not None` gate stays unset (receiver disabled) otherwise.
if bashio::config.has_value 'rx_gpio_pin'; then
    RX_GPIO_PIN=$(bashio::config 'rx_gpio_pin')
    SPI_SCK=$(bashio::config 'spi_sck')
    SPI_MOSI=$(bashio::config 'spi_mosi')
    SPI_MISO=$(bashio::config 'spi_miso')
    SPI_CSN=$(bashio::config 'spi_csn')
    bashio::log.info "RX receiver enabled: GPIO ${RX_GPIO_PIN} (CC1101)"

    for entry in "RXGPIO:${RX_GPIO_PIN}" "RXSpiSCK:${SPI_SCK}" "RXSpiMOSI:${SPI_MOSI}" "RXSpiMISO:${SPI_MISO}" "RXSpiCSN:${SPI_CSN}"; do
        key="${entry%%:*}"
        value="${entry#*:}"
        if grep -q "^${key}" "${CONFIG_FILE}"; then
            sed -i "s/^${key}.*/${key} = ${value}/" "${CONFIG_FILE}"
        else
            sed -i "/^\[General\]/a ${key} = ${value}" "${CONFIG_FILE}"
        fi
    done
else
    bashio::log.info "RX receiver disabled (set rx_gpio_pin in add-on options to enable)"
fi

# Ensure log location exists and is writable
sed -i "s|^LogLocation.*|LogLocation = /data/|" "${CONFIG_FILE}"

# Detect Pi model — Pi 5 uses lgpio (no daemon), older Pis use pigpio (needs pigpiod)
# /proc/device-tree/model may not be accessible inside the container; fall back to
# checking for /dev/gpiochip4 (RP1 chip, Pi 5 only) or the CPU revision code.
IS_PI5=false
PI_MODEL="unknown"
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
fi
bashio::log.info "Detected board: ${PI_MODEL}"

# Log available gpiochip devices for diagnostics
bashio::log.info "Available gpiochip devices: $(ls /dev/gpiochip* 2>/dev/null || echo 'none')"

if echo "${PI_MODEL}" | grep -q "Pi 5"; then
    IS_PI5=true
elif [ -e /dev/gpiochip4 ]; then
    bashio::log.info "/dev/gpiochip4 found — assuming Pi 5"
    IS_PI5=true
elif grep -q "^Revision.*[[:space:]].*[cd]0[34]17" /proc/cpuinfo 2>/dev/null; then
    bashio::log.info "Pi 5 CPU revision detected in /proc/cpuinfo"
    IS_PI5=true
fi

if [ "${IS_PI5}" = true ]; then
    bashio::log.info "Pi 5 detected — using lgpio (no pigpiod needed)"
else
    bashio::log.info "Starting pigpiod..."
    # Deliberately not passing -m (disable alerts): -m silently prevents
    # pi.callback() from ever delivering edge notifications, which the RX
    # receiver needs when rx_gpio_pin is set.
    pigpiod -l
    sleep 1

    if ! pgrep -x pigpiod > /dev/null; then
        bashio::log.error "Failed to start pigpiod!"
        exit 1
    fi

    bashio::log.info "pigpiod started successfully"
fi

# Launch Pi-Somfy with web interface only (no MQTT, no Alexa)
cd /somfy
bashio::log.info "Starting Pi-Somfy..."
exec python3 operateShutters.py -c "${CONFIG_FILE}" -a
