"""Light entity for Creality K2 SE 4C enclosure LED."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Creality K2 LED light."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CrealityK2Light(coordinator)])


class CrealityK2Light(CrealityK2Entity, LightEntity):
    """Representation of the Creality K2 enclosure LED light."""

    _attr_name = "Luz LED da Impressora"
    _attr_icon = "mdi:led-strip-variant"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, "led_light")

    @property
    def is_on(self) -> bool:
        """Return true if the LED is on."""
        return bool((self.coordinator.data or {}).get("light_on", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the printer LED via WebSocket and fallback G-code."""
        ok = await self.coordinator.async_send_ws_command({"lightSw": 1})
        if not ok:
            await self.coordinator.async_send_gcode("SET_PIN PIN=LED VALUE=1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the printer LED via WebSocket and fallback G-code."""
        ok = await self.coordinator.async_send_ws_command({"lightSw": 0})
        if not ok:
            await self.coordinator.async_send_gcode("SET_PIN PIN=LED VALUE=0")
        await self.coordinator.async_request_refresh()
