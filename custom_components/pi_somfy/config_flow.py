"""Config flow for Pi-Somfy integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=5, max=300)
        ),
    }
)


class PiSomfyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pi-Somfy."""

    VERSION = 1

    _hassio_host: str | None = None
    _hassio_port: int = DEFAULT_PORT

    async def _async_validate_connection(
        self, host: str, port: int, password: str
    ) -> dict[str, str]:
        """Validate we can connect to Pi-Somfy and return any errors."""
        session = async_get_clientsession(self.hass)
        headers: dict[str, str] = {}
        if password:
            headers["Password"] = password
        try:
            async with session.get(
                f"http://{host}:{port}/cmd/getConfig",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    return {"base": "invalid_auth"}
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                if "Shutters" not in data:
                    return {"base": "cannot_connect"}
        except (aiohttp.ClientError, TimeoutError):
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step from the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_connection(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD, ""),
            )
            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Pi-Somfy ({user_input[CONF_HOST]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle discovery from the Pi-Somfy add-on."""
        self._hassio_host = discovery_info.get("host", "local-pi-somfy")
        self._hassio_port = discovery_info.get("port", DEFAULT_PORT)

        await self.async_set_unique_id(f"{self._hassio_host}:{self._hassio_port}")
        self._abort_if_unique_id_configured()

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the Pi-Somfy add-on discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title="Pi-Somfy (Add-on)",
                data={
                    CONF_HOST: self._hassio_host,
                    CONF_PORT: self._hassio_port,
                    CONF_PASSWORD: "",
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={
                "host": self._hassio_host,
                "port": str(self._hassio_port),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_connection(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD, ""),
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data.get(CONF_HOST, "")
                    ): str,
                    vol.Required(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=entry.data.get(CONF_PASSWORD, ""),
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=entry.data.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                }
            ),
            errors=errors,
        )
