"""Cover platform for Pi-Somfy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PiSomfyConfigEntry
from .const import DOMAIN
from .coordinator import PiSomfyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiSomfyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pi-Somfy covers from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        PiSomfyCover(coordinator, shutter_id, entry)
        for shutter_id in coordinator.data
    )


class PiSomfyCover(CoordinatorEntity[PiSomfyCoordinator], CoverEntity):
    """Representation of a Pi-Somfy shutter."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PiSomfyCoordinator,
        shutter_id: str,
        entry: PiSomfyConfigEntry,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator, context=shutter_id)
        self._shutter_id = shutter_id
        self._attr_unique_id = f"{entry.entry_id}_{shutter_id}"
        shutter_data = coordinator.data.get(shutter_id, {})
        self._attr_name = shutter_data.get("name", shutter_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Pi-Somfy Bridge",
            manufacturer="Nickduino",
            model="Pi-Somfy RTS Gateway",
            configuration_url=coordinator.base_url,
        )
        self._moving: str | None = None  # 'opening', 'closing', or None

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return supported features, only including STOP when moving."""
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )
        if self._moving is not None:
            features |= CoverEntityFeature.STOP
        return features

    @property
    def current_cover_position(self) -> int | None:
        """Return current position (0=closed, 100=open)."""
        shutter = self.coordinator.data.get(self._shutter_id)
        if shutter is None:
            return None
        return shutter.get("position")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._moving == "opening"

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._moving == "closing"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Reads Pi-Somfy's own movement-state signal (populated by any trigger
        source — the app, a physical remote, or the web UI — not just
        commands issued through Home Assistant) rather than only clearing
        the optimistic local flag once position settles. This overwrites
        the optimistic set from async_open_cover/async_close_cover/
        async_set_cover_position with the server-authoritative value as soon
        as the next poll lands, which also happens to confirm HA-issued
        commands almost immediately since the coordinator refreshes right
        after sending one.
        """
        shutter = self.coordinator.data.get(self._shutter_id)
        if shutter is not None:
            state = shutter.get("movementState")
            self._moving = state if state in ("opening", "closing") else None
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._moving = "opening"
        self.async_write_ha_state()
        await self.coordinator.async_send_command("up", self._shutter_id)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._moving = "closing"
        self.async_write_ha_state()
        await self.coordinator.async_send_command("down", self._shutter_id)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._moving = None
        self.async_write_ha_state()
        await self.coordinator.async_send_command("stop", self._shutter_id)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get("position", 0)
        pos = self.current_cover_position
        if pos is not None and position > pos:
            self._moving = "opening"
        elif pos is not None and position < pos:
            self._moving = "closing"
        self.async_write_ha_state()
        await self.coordinator.async_send_command(
            "setPosition", self._shutter_id, position=position
        )
        await self.coordinator.async_request_refresh()
