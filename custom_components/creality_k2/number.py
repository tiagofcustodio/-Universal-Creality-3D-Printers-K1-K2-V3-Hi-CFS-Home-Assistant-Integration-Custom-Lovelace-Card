"""Number entities for Universal Creality Printers (Target Temperatures, Fan Speeds, Print Speed/Flow)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity


@dataclass(frozen=True, kw_only=True)
class CrealityK2NumberDescription(NumberEntityDescription):
    """Describe a Creality controllable number entity."""

    value_fn: Callable[[dict[str, Any]], float]
    set_value_fn: Callable[[CrealityK2Coordinator, float], Awaitable[None]]


async def _set_nozzle_target(coord: CrealityK2Coordinator, val: float) -> None:
    temp = int(round(val))
    ok = await coord.async_send_ws_command({"nozzleTempControl": temp})
    if not ok:
        await coord.async_send_gcode(f"M104 S{temp}")


async def _set_bed_target(coord: CrealityK2Coordinator, val: float) -> None:
    temp = int(round(val))
    ok = await coord.async_send_ws_command({"bedTemp0": temp})
    if not ok:
        await coord.async_send_gcode(f"M140 S{temp}")


async def _set_model_fan(coord: CrealityK2Coordinator, val: float) -> None:
    pct = int(round(val))
    s_val = int(round((pct / 100.0) * 255))
    await coord.async_send_gcode(f"M106 P0 S{s_val}")


async def _set_aux_fan(coord: CrealityK2Coordinator, val: float) -> None:
    pct = int(round(val))
    s_val = int(round((pct / 100.0) * 255))
    await coord.async_send_gcode(f"M106 P2 S{s_val}")


async def _set_case_fan(coord: CrealityK2Coordinator, val: float) -> None:
    pct = int(round(val))
    s_val = int(round((pct / 100.0) * 255))
    await coord.async_send_gcode(f"M106 P1 S{s_val}")


async def _set_feedrate(coord: CrealityK2Coordinator, val: float) -> None:
    pct = int(round(val))
    ok = await coord.async_send_ws_command({"curFeedratePct": pct})
    if not ok:
        await coord.async_send_gcode(f"M220 S{pct}")


async def _set_flowrate(coord: CrealityK2Coordinator, val: float) -> None:
    pct = int(round(val))
    ok = await coord.async_send_ws_command({"curFlowratePct": pct})
    if not ok:
        await coord.async_send_gcode(f"M221 S{pct}")


NUMBERS: tuple[CrealityK2NumberDescription, ...] = (
    CrealityK2NumberDescription(
        key="nozzle_target",
        name="Temperatura Alvo do Bico",
        icon="mdi:printer-3d-nozzle-heat-outline",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=350,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: float(d.get("nozzle_target", 0)),
        set_value_fn=_set_nozzle_target,
    ),
    CrealityK2NumberDescription(
        key="bed_target",
        name="Temperatura Alvo da Mesa",
        icon="mdi:radiator",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=120,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: float(d.get("bed_target", 0)),
        set_value_fn=_set_bed_target,
    ),
    CrealityK2NumberDescription(
        key="model_fan_pct",
        name="Ventoinha de Peça (Part Fan)",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: float(d.get("model_fan_pct", 0)),
        set_value_fn=_set_model_fan,
    ),
    CrealityK2NumberDescription(
        key="aux_fan_pct",
        name="Ventoinha Auxiliar Lateral",
        icon="mdi:fan-chevron-up",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: float(d.get("aux_fan_pct", 0)),
        set_value_fn=_set_aux_fan,
    ),
    CrealityK2NumberDescription(
        key="case_fan_pct",
        name="Ventoinha Traseira / Exaustão (Back Fan)",
        icon="mdi:fan-clock",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: float(d.get("case_fan_pct", 0)),
        set_value_fn=_set_case_fan,
    ),
    CrealityK2NumberDescription(
        key="feedrate_pct",
        name="Velocidade de Impressão (%)",
        icon="mdi:speedometer",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=10,
        native_max_value=300,
        native_step=5,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: float(d.get("feedrate_pct", 100)),
        set_value_fn=_set_feedrate,
    ),
    CrealityK2NumberDescription(
        key="flowrate_pct",
        name="Fluxo de Extrusão (%)",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=50,
        native_max_value=150,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: float(d.get("flowrate_pct", 100)),
        set_value_fn=_set_flowrate,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Creality number entities."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CrealityK2Number(coordinator, desc) for desc in NUMBERS
    )


class CrealityK2Number(CrealityK2Entity, NumberEntity):
    """Representation of a Creality controllable number."""

    entity_description: CrealityK2NumberDescription

    def __init__(
        self,
        coordinator: CrealityK2Coordinator,
        description: CrealityK2NumberDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    async def async_set_native_value(self, value: float) -> None:
        """Set a new target value."""
        await self.entity_description.set_value_fn(self.coordinator, value)
        await self.coordinator.async_request_refresh()
