"""Select entities for Creality K2 SE 4C (Speed Mode, CFS Active Slot, Stored G-Code File Selector)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SPEED_MODES
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity

REVERSE_SPEED_MODES = {v: k for k, v in SPEED_MODES.items()}
CFS_SLOTS = ["T1A", "T1B", "T1C", "T1D"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Creality K2 select entities."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CrealityK2SpeedModeSelect(coordinator),
            CrealityK2CFSSlotSelect(coordinator),
            CrealityK2GcodeFileSelect(coordinator),
        ]
    )


class CrealityK2SpeedModeSelect(CrealityK2Entity, SelectEntity):
    """Select entity for printer speed profile (Normal, Quiet, Sport)."""

    _attr_name = "Modo de Velocidade"
    _attr_icon = "mdi:car-speed-limiter"
    _attr_options = list(SPEED_MODES.values())

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the speed mode select."""
        super().__init__(coordinator, "speed_mode_select")

    @property
    def current_option(self) -> str:
        """Return the current speed mode."""
        mode_id = int((self.coordinator.data or {}).get("speed_mode", 0))
        return SPEED_MODES.get(mode_id, SPEED_MODES[0])

    async def async_select_option(self, option: str) -> None:
        """Change the printer speed mode."""
        mode_id = REVERSE_SPEED_MODES.get(option, 0)
        if mode_id == 1:
            await self.coordinator.async_send_gcode("Qmode")
        else:
            await self.coordinator.async_send_gcode("Qmode_exit")
        await self.coordinator.async_send_ws_command({"speedMode": mode_id})
        await self.coordinator.async_request_refresh()


class CrealityK2CFSSlotSelect(CrealityK2Entity, SelectEntity):
    """Select entity to load one of the 4 CFS filament slots (T1A - T1D)."""

    _attr_name = "CFS Selecionar / Carregar Bobine"
    _attr_icon = "mdi:palette-swatch-variant"
    _attr_options = CFS_SLOTS

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the CFS slot selector."""
        super().__init__(coordinator, "cfs_slot_select")

    @property
    def current_option(self) -> str | None:
        """Return currently active CFS slot."""
        active = (self.coordinator.data or {}).get("cfs_active_slot")
        return active if active in CFS_SLOTS else CFS_SLOTS[0]

    async def async_select_option(self, option: str) -> None:
        """Trigger CFS tool change / filament load for the selected slot."""
        slot_map = {"T1A": "T0", "T1B": "T1", "T1C": "T2", "T1D": "T3"}
        t_cmd = slot_map.get(option, "T0")
        await self.coordinator.async_send_gcode(t_cmd)
        await self.coordinator.async_request_refresh()


class CrealityK2GcodeFileSelect(CrealityK2Entity, SelectEntity):
    """Select entity to browse G-code files stored on the printer and preview their 3D thumbnail."""

    _attr_name = "Selecionar Ficheiro G-Code Guardado"
    _attr_icon = "mdi:file-image-outline"

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the G-code file selector."""
        super().__init__(coordinator, "gcode_file_select")

    @property
    def options(self) -> list[str]:
        """Return list of recent G-code files on printer."""
        files = (self.coordinator.data or {}).get("available_files", [])
        return files if files else ["Nenhum ficheiro encontrado"]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected file for preview/start."""
        opts = self.options
        selected = self.coordinator.selected_preview_file
        if selected and selected in opts:
            return selected
        current = (self.coordinator.data or {}).get("filename")
        if current and current in opts:
            return current
        return opts[0] if opts else None

    async def async_select_option(self, option: str) -> None:
        """Select the file to preview its 3D image (and warm up thumbnail cache)."""
        if option == "Nenhum ficheiro encontrado":
            return
        self.coordinator.selected_preview_file = option
        await self.coordinator.async_get_gcode_thumbnail(option)
        self.coordinator.async_set_updated_data(self.coordinator._build_merged_data())
