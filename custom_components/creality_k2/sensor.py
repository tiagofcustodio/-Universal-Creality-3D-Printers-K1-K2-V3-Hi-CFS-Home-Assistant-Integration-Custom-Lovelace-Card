"""Sensor entities for Universal Creality Printers (K1, K2, Ender-3 V3, Creality Hi + CFS)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity


@dataclass(frozen=True, kw_only=True)
class CrealityK2SensorDescription(SensorEntityDescription):
    """Describe a Creality sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]
    extra_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[CrealityK2SensorDescription, ...] = (
    CrealityK2SensorDescription(
        key="status",
        name="Estado da Impressora",
        icon="mdi:printer-3d",
        value_fn=lambda d: d.get("status", "standby"),
        extra_fn=lambda d: {
            "hostname": d.get("hostname"),
            "model": d.get("model"),
            "error_code": d.get("error_code", 0),
            "error_key": d.get("error_key", 0),
            "position": d.get("position"),
            "cfs_connected": d.get("cfs_connected", False),
        },
    ),
    CrealityK2SensorDescription(
        key="progress",
        name="Progresso de Impressão",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("progress", 0),
    ),
    CrealityK2SensorDescription(
        key="filename",
        name="Ficheiro Atual",
        icon="mdi:file-cad",
        value_fn=lambda d: d.get("filename") or "Nenhum",
    ),
    CrealityK2SensorDescription(
        key="layer_progress",
        name="Camada Atual",
        icon="mdi:layers-triple",
        value_fn=lambda d: f"{d.get('current_layer', 0)} / {d.get('total_layers', 0)}",
        extra_fn=lambda d: {
            "current_layer": d.get("current_layer", 0),
            "total_layers": d.get("total_layers", 0),
        },
    ),
    CrealityK2SensorDescription(
        key="current_layer_num",
        name="Número da Camada",
        icon="mdi:layers",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("current_layer", 0),
    ),
    CrealityK2SensorDescription(
        key="print_time_elapsed",
        name="Tempo Decorrido",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: round(d.get("print_job_time_s", 0) / 60, 1),
        extra_fn=lambda d: {"seconds": d.get("print_job_time_s", 0)},
    ),
    CrealityK2SensorDescription(
        key="print_time_remaining",
        name="Tempo Restante",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: round(d.get("print_left_time_s", 0) / 60, 1),
        extra_fn=lambda d: {"seconds": d.get("print_left_time_s", 0)},
    ),
    CrealityK2SensorDescription(
        key="nozzle_temp",
        name="Temperatura do Bico",
        icon="mdi:printer-3d-nozzle-heat",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("nozzle_temp", 0.0),
        extra_fn=lambda d: {"target": d.get("nozzle_target", 0.0)},
    ),
    CrealityK2SensorDescription(
        key="bed_temp",
        name="Temperatura da Mesa",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("bed_temp", 0.0),
        extra_fn=lambda d: {"target": d.get("bed_target", 0.0)},
    ),
    CrealityK2SensorDescription(
        key="chamber_temp",
        name="Temperatura da Câmara",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("chamber_temp", 0.0),
    ),
    CrealityK2SensorDescription(
        key="mcu_temp",
        name="Temperatura MCU",
        icon="mdi:chip",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("mcu_temp", 0.0),
    ),
    CrealityK2SensorDescription(
        key="realtime_speed",
        name="Velocidade em Tempo Real",
        icon="mdi:speedometer",
        native_unit_of_measurement="mm/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("realtime_speed_mms", 0.0),
    ),
    CrealityK2SensorDescription(
        key="realtime_flow",
        name="Fluxo em Tempo Real (Volumétrico)",
        icon="mdi:water-outline",
        native_unit_of_measurement="mm³/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("realtime_flow_mm3s", 0.0),
    ),
    CrealityK2SensorDescription(
        key="used_material",
        name="Filamento Usado na Impressão",
        icon="mdi:spool",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.get("used_material_mm", 0.0) / 1000.0, 2),
    ),
    CrealityK2SensorDescription(
        key="fan0_rpm",
        name="RPM Ventoinha do Bico",
        icon="mdi:fan",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("fan0_rpm", 0),
    ),
    # CFS Multi-Color System Sensors
    CrealityK2SensorDescription(
        key="cfs_active_slot",
        name="CFS Slot Ativo",
        icon="mdi:palette-swatch",
        value_fn=lambda d: d.get("cfs_active_slot", "Nenhum"),
        extra_fn=lambda d: {
            "cfs_type": d.get("cfs_type", "CFS"),
            "auto_refill": d.get("cfs_auto_refill", False),
        },
    ),
    CrealityK2SensorDescription(
        key="cfs_humidity",
        name="CFS Humidade",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("box_humidity", 0),
    ),
    CrealityK2SensorDescription(
        key="cfs_temperature",
        name="CFS Temperatura",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("box_temp", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Creality sensors from config entry."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        CrealityK2Sensor(coordinator, desc) for desc in SENSORS
    ]

    # Add CFS slot sensors for all connected CFS units (T1A..T1D by default, up to T4D for 16-color setups)
    slot_num = 1
    for unit_id in coordinator.detected_cfs_units:
        for letter in ("A", "B", "C", "D"):
            slot_key = f"{unit_id}{letter}"
            entities.append(CrealityK2CFSSlotSensor(coordinator, slot_key, slot_num))
            slot_num += 1

    async_add_entities(entities)


class CrealityK2Sensor(CrealityK2Entity, SensorEntity):
    """Representation of a Creality telemetry sensor."""

    entity_description: CrealityK2SensorDescription

    def __init__(
        self,
        coordinator: CrealityK2Coordinator,
        description: CrealityK2SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_fn:
            return self.entity_description.extra_fn(self.coordinator.data or {})
        return None


class CrealityK2CFSSlotSensor(CrealityK2Entity, SensorEntity):
    """Sensor representing a filament slot (e.g. T1A - T4D) in the Creality CFS."""

    def __init__(
        self, coordinator: CrealityK2Coordinator, slot_key: str, slot_num: int
    ) -> None:
        """Initialize the CFS slot sensor."""
        super().__init__(coordinator, f"cfs_slot_{slot_key.lower()}")
        self._slot_key = slot_key
        self._attr_name = f"CFS Slot {slot_num} ({slot_key})"
        self._attr_icon = "mdi:printer-3d-nozzle"

    @property
    def native_value(self) -> str:
        """Return material name and loaded status for this slot."""
        slots = (self.coordinator.data or {}).get("cfs_slots", {})
        slot_info = slots.get(self._slot_key, {})
        material = slot_info.get("material", "Vazio")
        color_hex = slot_info.get("color_hex", "#808080")
        loaded = slot_info.get("loaded", False)
        status_tag = " [Em Uso]" if loaded else ""
        return f"{material} ({color_hex}){status_tag}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rich color and filament details for dashboard cards."""
        slots = (self.coordinator.data or {}).get("cfs_slots", {})
        slot_info = slots.get(self._slot_key, {})
        return {
            "slot": self._slot_key,
            "material": slot_info.get("material", "Vazio"),
            "material_code": slot_info.get("material_code", "-1"),
            "color_hex": slot_info.get("color_hex", "#808080"),
            "loaded": slot_info.get("loaded", False),
            "empty": slot_info.get("empty", True),
            "vendor": slot_info.get("vendor", "unknown"),
            "remain_length": slot_info.get("remain_length", "-1"),
        }
