"""Base entity for Universal Creality Klipper / K-Series printers."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CREALITY_MODEL_MAP, DOMAIN
from .coordinator import CrealityK2Coordinator


class CrealityK2Entity(CoordinatorEntity[CrealityK2Coordinator]):
    """Common base class for all Creality printer entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CrealityK2Coordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.host}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device registry information based on the detected Creality model."""
        data = self.coordinator.data or {}
        hostname = data.get("hostname", self.coordinator.host)
        raw_model = str(data.get("model", "")).strip()
        friendly_model = CREALITY_MODEL_MAP.get(raw_model, raw_model or "Creality K-Series")
        cfs_connected = data.get("cfs_connected", False)
        cfs_type = data.get("cfs_type", "")
        if cfs_connected and cfs_type:
            model_display = f"{friendly_model} ({raw_model} + {cfs_type})"
        elif raw_model and raw_model != friendly_model:
            model_display = f"{friendly_model} ({raw_model})"
        else:
            model_display = friendly_model

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"{friendly_model} ({hostname})",
            manufacturer="Creality",
            model=model_display,
            sw_version=data.get("sw_version", "Creality OS / Klipper"),
            configuration_url=f"http://{self.coordinator.host}",
        )
