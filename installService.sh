#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${PI_SOMFY_CONFIG:-$APP_DIR/operateShutters.conf}"
SERVICE_NAME="${PI_SOMFY_SERVICE_NAME:-pi-somfy}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_ARGS="${PI_SOMFY_ARGS:--a}"

if [ -n "${PI_SOMFY_PYTHON:-}" ]; then
    PYTHON_BIN="$PI_SOMFY_PYTHON"
elif [ -x "$APP_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$APP_DIR/.venv/bin/python"
else
    PYTHON_BIN="/usr/bin/python3"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    cp "$APP_DIR/defaultConfig.conf" "$CONFIG_FILE"
fi

if [ "$(id -u)" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

# Default service unit: pi-somfy.service
"${SUDO[@]}" tee "$SERVICE_FILE" >/dev/null <<SERVICE
[Unit]
Description=Pi Somfy Shutter Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON_BIN $APP_DIR/operateShutters.py -c $CONFIG_FILE $APP_ARGS
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable "${SERVICE_NAME}.service"
"${SUDO[@]}" systemctl restart "${SERVICE_NAME}.service"
"${SUDO[@]}" systemctl --no-pager --full status "${SERVICE_NAME}.service"
