#!/usr/bin/with-contenv bashio

RX_GPIO_PIN=$(bashio::config 'rx_gpio_pin')
SPI_SCK=$(bashio::config 'spi_sck')
SPI_MOSI=$(bashio::config 'spi_mosi')
SPI_MISO=$(bashio::config 'spi_miso')
SPI_CSN=$(bashio::config 'spi_csn')
TEST_TX_INTERVAL=$(bashio::config 'test_tx_interval')
TX_GPIO_PIN=$(bashio::config 'tx_gpio_pin')
MQTT_HOST=$(bashio::config 'mqtt_host')
MQTT_PORT=$(bashio::config 'mqtt_port')
MQTT_USER=$(bashio::config 'mqtt_user')
MQTT_PASSWORD=$(bashio::config 'mqtt_password')

bashio::log.info "RTS Sniffer POC starting..."
bashio::log.info "RX: GPIO ${RX_GPIO_PIN} (CC1101)"

# Detect Pi model — Pi 5 uses lgpio (no daemon), older Pis use pigpio (needs
# pigpiod). Same detection as the pi_somfy add-on: /proc/device-tree/model may
# not be accessible inside the container; fall back to /dev/gpiochip4 (RP1
# chip, Pi 5 only) or the CPU revision code.
IS_PI5=false
PI_MODEL="unknown"
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
fi
bashio::log.info "Detected board: ${PI_MODEL}"
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
    # -f disables the legacy pipe/FIFO command interface (/dev/pigpio): the
    # sniffer only ever talks to pigpiod over its TCP socket interface anyway.
    # Deliberately NOT passing -m (disable alerts): alerts are the mechanism
    # pi.callback() uses to deliver edge notifications, which this receiver
    # needs — unlike operateShutters.py's TX-only pigpiod startup, which
    # never needed alerts and passes -m.
    pigpiod -l -f
    sleep 1

    if ! pgrep -x pigpiod > /dev/null; then
        bashio::log.error "Failed to start pigpiod!"
        bashio::log.error "Is the Pi-Somfy add-on still running? Two pigpiod daemons cannot share DMA//dev/mem — stop Pi-Somfy while the POC runs."
        exit 1
    fi

    bashio::log.info "pigpiod started successfully"
fi

ARGS="--rx-gpio ${RX_GPIO_PIN}"
ARGS="${ARGS} --spi-sck ${SPI_SCK} --spi-mosi ${SPI_MOSI} --spi-miso ${SPI_MISO} --spi-csn ${SPI_CSN}"
ARGS="${ARGS} --test-tx-interval ${TEST_TX_INTERVAL} --tx-gpio ${TX_GPIO_PIN}"
if bashio::var.has_value "${MQTT_HOST}"; then
    ARGS="${ARGS} --mqtt-host ${MQTT_HOST} --mqtt-port ${MQTT_PORT}"
    if bashio::var.has_value "${MQTT_USER}"; then
        ARGS="${ARGS} --mqtt-user ${MQTT_USER} --mqtt-password ${MQTT_PASSWORD}"
    fi
fi

bashio::log.info "Starting sniffer..."
# shellcheck disable=SC2086
exec python3 /sniffer.py ${ARGS}
