"""Binary sensor entities for Creality K2 SE 4C."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity


@dataclass(frozen=True, kw_only=True)
class CrealityK2BinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Creality K2 binary sensor."""

    is_on_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[CrealityK2BinarySensorDescription, ...] = (
    CrealityK2BinarySensorDescription(
        key="printing",
        name="Em Impressão",
        icon="mdi:printer-3d-nozzle",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda d: d.get("status") == "printing",
    ),
    CrealityK2BinarySensorDescription(
        key="filament_detected",
        name="Filamento Detetado no Extrusor",
        icon="mdi:spool",
        is_on_fn=lambda d: bool(d.get("filament_detected", True)),
    ),
    CrealityK2BinarySensorDescription(
        key="cfs_connected",
        name="CFS 4 Cores Ligado",
        icon="mdi:palette",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda d: bool(d.get("cfs_connected", False)),
    ),
    CrealityK2BinarySensorDescription(
        key="has_error",
        name="Erro na Impressora",
        icon="mdi:alert-circle",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: int(d.get("error_code", 0)) != 0
        or d.get("status") == "error",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Creality K2 binary sensors."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CrealityK2BinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class CrealityK2BinarySensor(CrealityK2Entity, BinarySensorEntity):
    """Representation of a Creality K2 binary sensor."""

    entity_description: CrealityK2BinarySensorDescription

    def __init__(
        self,
        coordinator: CrealityK2Coordinator,
        description: CrealityK2BinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data or {})
