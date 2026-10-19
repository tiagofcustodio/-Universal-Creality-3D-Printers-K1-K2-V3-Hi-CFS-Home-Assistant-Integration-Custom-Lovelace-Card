"""The Creality K2 SE 4C integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CAMERA_URL,
    CONF_HOST,
    CONF_MOONRAKER_PORT,
    CONF_WS_PORT,
    DEFAULT_MOONRAKER_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
    SERVICE_CFS_LOAD,
    SERVICE_CFS_REFRESH,
    SERVICE_CFS_UNLOAD,
    SERVICE_SEND_GCODE,
    SERVICE_START_PRINT,
)
from .coordinator import CrealityK2Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.CAMERA,
]

CARD_URL_PATH = "/creality_k2/creality-k2-card.js"

_FALLBACK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x60\x60"
    b"\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class CrealityK2ThumbnailView(HomeAssistantView):
    """Direct HTTP view to serve 300x300 PNG thumbnails for any stored G-code file immediately."""

    url = "/api/creality_k2/thumbnail"
    name = "api:creality_k2:thumbnail"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the thumbnail HTTP view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the PNG thumbnail for ?file=<filename>."""
        filename = request.query.get("file", "").strip()
        coords: list[CrealityK2Coordinator] = [
            v
            for v in self.hass.data.get(DOMAIN, {}).values()
            if isinstance(v, CrealityK2Coordinator)
        ]
        if coords and filename:
            coord = coords[0]
            img_bytes = await coord.async_get_gcode_thumbnail(filename)
            if img_bytes:
                return web.Response(
                    body=img_bytes,
                    content_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"},
                )

        return web.Response(
            body=_FALLBACK_PNG,
            content_type="image/png",
            headers={"Cache-Control": "no-cache"},
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Creality K2 SE 4C from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register the static path, thumbnail API view, and inject JS into Home Assistant frontend
    www_dir = Path(__file__).parent / "www"
    card_file = www_dir / "creality-k2-card.js"
    if not hass.data[DOMAIN].get("_static_registered"):
        try:
            if card_file.is_file():
                await hass.http.async_register_static_paths(
                    [StaticPathConfig(CARD_URL_PATH, str(card_file), cache_headers=False)]
                )
                add_extra_js_url(hass, f"{CARD_URL_PATH}?v=1.3.0")
            hass.http.register_view(CrealityK2ThumbnailView(hass))
            hass.data[DOMAIN]["_static_registered"] = True
        except Exception as err:
            _LOGGER.debug("Static path / frontend registration note: %s", err)

    host = entry.data[CONF_HOST]
    moonraker_port = entry.data.get(CONF_MOONRAKER_PORT, DEFAULT_MOONRAKER_PORT)
    ws_port = entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT)
    camera_url = entry.data.get(CONF_CAMERA_URL)

    coordinator = CrealityK2Coordinator(
        hass=hass,
        host=host,
        moonraker_port=moonraker_port,
        ws_port=ws_port,
        camera_url=camera_url,
    )

    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_websocket()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: CrealityK2Coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop_websocket()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _get_target_coordinators(
    hass: HomeAssistant, call: ServiceCall
) -> list[CrealityK2Coordinator]:
    """Return all active CrealityK2Coordinators (or filtered by host if specified)."""
    target_host = call.data.get("host")
    coords: list[CrealityK2Coordinator] = [
        v for k, v in hass.data.get(DOMAIN, {}).items() if isinstance(v, CrealityK2Coordinator)
    ]
    if target_host:
        return [c for c in coords if c.host == target_host]
    return coords


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services for Creality K2 SE 4C."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_GCODE):
        return

    async def handle_send_gcode(call: ServiceCall) -> None:
        script = call.data["gcode"]
        for coord in _get_target_coordinators(hass, call):
            await coord.async_send_gcode(script)
            await coord.async_request_refresh()

    async def handle_start_print(call: ServiceCall) -> None:
        filename = call.data["filename"]
        for coord in _get_target_coordinators(hass, call):
            await coord.async_moonraker_post(
                "/printer/print/start", {"filename": filename}
            )
            await coord.async_request_refresh()

    async def handle_cfs_load(call: ServiceCall) -> None:
        slot = call.data["slot"].upper()
        slot_map = {"T1A": "T0", "T1B": "T1", "T1C": "T2", "T1D": "T3"}
        t_cmd = slot_map.get(slot, slot)
        for coord in _get_target_coordinators(hass, call):
            await coord.async_send_gcode(t_cmd)
            await coord.async_request_refresh()

    async def handle_cfs_unload(call: ServiceCall) -> None:
        for coord in _get_target_coordinators(hass, call):
            await coord.async_send_gcode("BOX_QUIT_MATERIAL")
            await coord.async_request_refresh()

    async def handle_cfs_refresh(call: ServiceCall) -> None:
        for coord in _get_target_coordinators(hass, call):
            await coord.async_send_gcode("BOX_INFO_REFRESH")
            await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_GCODE,
        handle_send_gcode,
        schema=vol.Schema(
            {
                vol.Required("gcode"): cv.string,
                vol.Optional("host"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_PRINT,
        handle_start_print,
        schema=vol.Schema(
            {
                vol.Required("filename"): cv.string,
                vol.Optional("host"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CFS_LOAD,
        handle_cfs_load,
        schema=vol.Schema(
            {
                vol.Required("slot"): vol.In(["T1A", "T1B", "T1C", "T1D"]),
                vol.Optional("host"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CFS_UNLOAD,
        handle_cfs_unload,
        schema=vol.Schema({vol.Optional("host"): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CFS_REFRESH,
        handle_cfs_refresh,
        schema=vol.Schema({vol.Optional("host"): cv.string}),
    )
