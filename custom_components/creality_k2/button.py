"""Button entities for Creality K2 SE 4C (Start Selected File, Pause, Resume, Stop, Home, CFS Actions)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity


@dataclass(frozen=True, kw_only=True)
class CrealityK2ButtonDescription(ButtonEntityDescription):
    """Describe a Creality K2 button entity."""

    press_fn: Callable[[CrealityK2Coordinator], Awaitable[None]]


async def _start_selected_file(coord: CrealityK2Coordinator) -> None:
    target_file = coord.selected_preview_file or (coord.data or {}).get("selected_preview_file")
    if target_file and target_file != "Nenhum ficheiro encontrado":
        await coord.async_moonraker_post(
            "/printer/print/start", {"filename": target_file}
        )


async def _pause_print(coord: CrealityK2Coordinator) -> None:
    ok = await coord.async_moonraker_post("/printer/print/pause")
    if not ok:
        await coord.async_send_ws_command({"pause": 1})


async def _resume_print(coord: CrealityK2Coordinator) -> None:
    ok = await coord.async_moonraker_post("/printer/print/resume")
    if not ok:
        await coord.async_send_ws_command({"pause": 0})


async def _cancel_print(coord: CrealityK2Coordinator) -> None:
    ok = await coord.async_moonraker_post("/printer/print/cancel")
    if not ok:
        await coord.async_send_ws_command({"stop": 1})


BUTTONS: tuple[CrealityK2ButtonDescription, ...] = (
    CrealityK2ButtonDescription(
        key="start_selected_print",
        name="Imprimir Ficheiro G-Code Selecionado",
        icon="mdi:printer-3d-nozzle-outline",
        press_fn=_start_selected_file,
    ),
    CrealityK2ButtonDescription(
        key="pause_print",
        name="Pausar Impressão",
        icon="mdi:pause-circle",
        press_fn=_pause_print,
    ),
    CrealityK2ButtonDescription(
        key="resume_print",
        name="Retomar Impressão",
        icon="mdi:play-circle",
        press_fn=_resume_print,
    ),
    CrealityK2ButtonDescription(
        key="cancel_print",
        name="Cancelar / Parar Impressão",
        icon="mdi:stop-circle",
        press_fn=_cancel_print,
    ),
    CrealityK2ButtonDescription(
        key="home_axes",
        name="Home Todos os Eixos (G28)",
        icon="mdi:home-import-outline",
        press_fn=lambda c: c.async_send_gcode("G28"),
    ),
    CrealityK2ButtonDescription(
        key="cfs_refresh",
        name="CFS Atualizar Slots RFID",
        icon="mdi:refresh-circle",
        press_fn=lambda c: c.async_send_gcode("BOX_INFO_REFRESH"),
    ),
    CrealityK2ButtonDescription(
        key="cfs_unload",
        name="CFS Retrair / Descarregar Filamento",
        icon="mdi:eject",
        press_fn=lambda c: c.async_send_gcode("BOX_QUIT_MATERIAL"),
    ),
    CrealityK2ButtonDescription(
        key="emergency_stop",
        name="Paragem de Emergência",
        icon="mdi:alert-octagon",
        press_fn=lambda c: c.async_moonraker_post("/printer/emergency_stop"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Creality K2 buttons."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CrealityK2Button(coordinator, desc) for desc in BUTTONS
    )


class CrealityK2Button(CrealityK2Entity, ButtonEntity):
    """Representation of a Creality K2 action button."""

    entity_description: CrealityK2ButtonDescription

    def __init__(
        self,
        coordinator: CrealityK2Coordinator,
        description: CrealityK2ButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Execute button action."""
        await self.entity_description.press_fn(self.coordinator)
        await self.coordinator.async_request_refresh()
