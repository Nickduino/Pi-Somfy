"""DataUpdateCoordinator for Pi-Somfy."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PiSomfyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to poll Pi-Somfy for shutter data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data[CONF_PORT]
        self._password: str = entry.data.get(CONF_PASSWORD, "")
        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self._session = async_get_clientsession(hass)

    @property
    def base_url(self) -> str:
        """Return the Pi-Somfy base URL."""
        return f"http://{self._host}:{self._port}"

    def _headers(self) -> dict[str, str]:
        """Return request headers including password if set."""
        headers: dict[str, str] = {}
        if self._password:
            headers["Password"] = self._password
        return headers

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch shutter status from Pi-Somfy."""
        try:
            async with self._session.get(
                f"{self.base_url}/cmd/getStatus",
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Invalid password")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except ConfigEntryAuthFailed:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with Pi-Somfy: {err}") from err

        if data.get("status") == "ERROR":
            raise UpdateFailed("Pi-Somfy returned an error status")

        return data.get("shutters", {})

    async def async_send_command(
        self, command: str, shutter_id: str, **kwargs: Any
    ) -> bool:
        """Send a command to Pi-Somfy."""
        params = {"shutter": shutter_id, **kwargs}
        try:
            async with self._session.get(
                f"{self.base_url}/cmd/{command}",
                headers=self._headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data.get("status") == "OK"
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error sending command %s: %s", command, err)
            return False
