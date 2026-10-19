"""Camera / 3D Thumbnail entities for Creality K2 SE 4C."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrealityK2Coordinator
from .entity import CrealityK2Entity

_LOGGER = logging.getLogger(__name__)

# Minimal 1x1 dark PNG fallback when no file is selected
_FALLBACK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x60\x60"
    b"\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Creality K2 camera / G-code 3D preview entities."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CrealityK2ActivePrintCamera(coordinator),
            CrealityK2SelectedFilePreviewCamera(coordinator),
        ]
    )


class CrealityK2ActivePrintCamera(CrealityK2Entity, Camera):
    """Camera entity showing live USB camera snapshot OR the 300x300 3D image of the active print."""

    _attr_name = "Câmara / Imagem da Impressão Atual"
    _attr_icon = "mdi:printer-3d"

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the active print camera entity."""
        CrealityK2Entity.__init__(self, coordinator, "camera_preview")
        Camera.__init__(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the filename currently displayed."""
        data = self.coordinator.data or {}
        return {
            "printing_file": data.get("filename") or "Nenhum",
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return live camera snapshot or embedded 300x300 PNG from the active G-code header."""
        # 1. Try custom camera URL or USB webcam snapshot on port 8080 if present
        urls_to_try = []
        if self.coordinator.camera_url:
            urls_to_try.append(self.coordinator.camera_url)
        urls_to_try.append(f"http://{self.coordinator.host}:8080/?action=snapshot")

        for url in urls_to_try:
            try:
                async with self.coordinator.session.get(url, timeout=2) as resp:
                    if resp.status == 200 and resp.content_type.startswith("image"):
                        return await resp.read()
            except Exception:
                continue

        # 2. Extract embedded 300x300 PNG directly from the active or selected G-code header
        data = self.coordinator.data or {}
        filename = data.get("filename") or data.get("selected_preview_file")
        if filename:
            thumb = await self.coordinator.async_get_gcode_thumbnail(filename)
            if thumb:
                return thumb

        return _FALLBACK_PNG


class CrealityK2SelectedFilePreviewCamera(CrealityK2Entity, Camera):
    """Camera entity showing the 300x300 3D preview of whichever stored G-code file is selected in the dropdown."""

    _attr_name = "Pré-visualização 3D do Ficheiro Selecionado"
    _attr_icon = "mdi:file-image"

    def __init__(self, coordinator: CrealityK2Coordinator) -> None:
        """Initialize the selected file preview camera entity."""
        CrealityK2Entity.__init__(self, coordinator, "selected_file_preview")
        Camera.__init__(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the selected filename being previewed."""
        data = self.coordinator.data or {}
        return {
            "selected_file": data.get("selected_preview_file") or "Nenhum",
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the embedded 300x300 PNG thumbnail of the selected G-code file."""
        data = self.coordinator.data or {}
        selected = (
            self.coordinator.selected_preview_file
            or data.get("selected_preview_file")
            or data.get("filename")
        )
        if selected:
            thumb = await self.coordinator.async_get_gcode_thumbnail(selected)
            if thumb:
                return thumb

        return _FALLBACK_PNG
