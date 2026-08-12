#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${PI_SOMFY_CONFIG:-$APP_DIR/operateShutters.conf}"

if [ -n "${PI_SOMFY_PYTHON:-}" ]; then
    PYTHON_BIN="$PI_SOMFY_PYTHON"
elif [ -x "$APP_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$APP_DIR/.venv/bin/python"
else
    PYTHON_BIN="/usr/bin/python3"
fi

if [ "$#" -eq 0 ]; then
    set -- -a -m -e
fi

exec "$PYTHON_BIN" "$APP_DIR/operateShutters.py" -c "$CONFIG_FILE" "$@"
