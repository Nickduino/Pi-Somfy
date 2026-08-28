"""The Pi-Somfy integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import PiSomfyCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]

type PiSomfyConfigEntry = ConfigEntry[PiSomfyCoordinator]

SERVICE_PROGRAM_SHUTTER = "program_shutter"
SERVICE_PRESS_BUTTONS = "press_buttons"

PROGRAM_SCHEMA = vol.Schema(
    {vol.Required("shutter_id"): cv.string}
)

PRESS_SCHEMA = vol.Schema(
    {
        vol.Required("shutter_id"): cv.string,
        vol.Required("buttons"): vol.All(int, vol.Range(min=0, max=15)),
        vol.Optional("long_press", default=False): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: PiSomfyConfigEntry) -> bool:
    """Set up Pi-Somfy from a config entry."""
    coordinator = PiSomfyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    async def handle_program_shutter(call: ServiceCall) -> None:
        """Handle the program_shutter service call."""
        shutter_id = call.data["shutter_id"]
        await coordinator.async_send_command("program", shutter_id)

    async def handle_press_buttons(call: ServiceCall) -> None:
        """Handle the press_buttons service call."""
        shutter_id = call.data["shutter_id"]
        buttons = call.data["buttons"]
        long_press = call.data.get("long_press", False)
        await coordinator.async_send_command(
            "press", shutter_id, buttons=buttons, longPress=str(long_press).lower()
        )

    hass.services.async_register(
        DOMAIN, SERVICE_PROGRAM_SHUTTER, handle_program_shutter, schema=PROGRAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PRESS_BUTTONS, handle_press_buttons, schema=PRESS_SCHEMA
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PiSomfyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
