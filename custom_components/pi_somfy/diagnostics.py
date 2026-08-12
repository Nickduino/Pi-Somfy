"""Diagnostics support for Pi-Somfy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import PiSomfyConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PiSomfyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "shutters": coordinator.data,
    }
