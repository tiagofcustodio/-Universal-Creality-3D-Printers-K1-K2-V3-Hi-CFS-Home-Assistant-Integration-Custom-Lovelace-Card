"""Config flow for Universal Creality Klipper / K-Series integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CAMERA_URL,
    CONF_HOST,
    CONF_MOONRAKER_PORT,
    CONF_WS_PORT,
    CREALITY_MODEL_MAP,
    DEFAULT_MOONRAKER_PORT,
    DEFAULT_WS_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_connection(
    hass: HomeAssistant, host: str, moonraker_port: int, ws_port: int
) -> dict[str, Any]:
    """Validate connection via Moonraker HTTP (port 7125) OR Native WebSocket (port 9999)."""
    session = async_get_clientsession(hass)
    result: dict[str, Any] = {"hostname": host, "model": "Creality 3D Printer"}

    # 1. Try Moonraker API (port 7125)
    mr_ok = False
    try:
        url = f"http://{host}:{moonraker_port}/printer/info"
        async with session.get(url, timeout=5) as resp:
            if resp.status == 200:
                body = await resp.json()
                info = body.get("result", {})
                if info.get("hostname"):
                    result["hostname"] = info["hostname"]
                mr_ok = True
    except Exception:
        pass

    # 2. Try Native Creality WebSocket (port 9999) — works even on non-rooted K1/Ender-3 V3
    ws_ok = False
    try:
        ws_url = f"ws://{host}:{ws_port}"
        async with session.ws_connect(ws_url, timeout=5) as ws:
            msg = await ws.receive(timeout=4)
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if isinstance(data, dict):
                    if data.get("hostname"):
                        result["hostname"] = data["hostname"]
                    raw_model = data.get("model", "")
                    if raw_model:
                        result["model"] = CREALITY_MODEL_MAP.get(raw_model, raw_model)
                    ws_ok = True
    except Exception:
        pass

    if not mr_ok and not ws_ok:
        raise aiohttp.ClientConnectionError(
            f"Cannot connect to Creality printer at {host} on ports {moonraker_port} or {ws_port}"
        )

    return result


class CrealityK2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Universal Creality K-Series / Klipper printers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            mr_port = user_input.get(CONF_MOONRAKER_PORT, DEFAULT_MOONRAKER_PORT)
            ws_port = user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT)

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_connection(self.hass, host, mr_port, ws_port)
                hostname = info.get("hostname", host)
                model = info.get("model", "Creality")
                return self.async_create_entry(
                    title=f"{model} ({hostname})",
                    data=user_input,
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=""): str,
                vol.Optional(
                    CONF_MOONRAKER_PORT, default=DEFAULT_MOONRAKER_PORT
                ): int,
                vol.Optional(CONF_WS_PORT, default=DEFAULT_WS_PORT): int,
                vol.Optional(CONF_CAMERA_URL, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
