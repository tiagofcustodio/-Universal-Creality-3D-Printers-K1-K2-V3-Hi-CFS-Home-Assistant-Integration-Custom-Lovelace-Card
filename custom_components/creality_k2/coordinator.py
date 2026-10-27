"""Coordinator and Hybrid Client (WebSocket 9999 + Moonraker 7125) for Universal Creality Printers."""
from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
import json
import logging
import re
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CFS_MATERIAL_MAP,
    DEFAULT_MOONRAKER_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WS_PORT,
    DOMAIN,
    EVENT_FILAMENT_RUNOUT,
    EVENT_LAYER_CHANGED,
    EVENT_PRINT_FAILED,
    EVENT_PRINT_FINISHED,
    EVENT_PRINT_PAUSED,
    EVENT_PRINT_STARTED,
    EVENT_PRINTER_ERROR,
)

_LOGGER = logging.getLogger(__name__)

_THUMBNAIL_PATTERN = re.compile(
    r";\s*thumbnail begin\s+(\d+)x(\d+)\s+\d+\r?\n(.*?);\s*thumbnail end",
    re.DOTALL,
)


def _parse_color_hex(raw_color: str | None) -> str:
    """Convert Creality CFS color code (e.g. '0ffffff' or '0ff1e1e') to '#RRGGBB'."""
    if not raw_color or raw_color in ("-1", "None"):
        return "#808080"
    cleaned = raw_color.strip().lstrip("#")
    if len(cleaned) == 7 and cleaned.startswith("0"):
        cleaned = cleaned[1:]
    if len(cleaned) == 6:
        return f"#{cleaned.upper()}"
    return "#808080"


class CrealityK2Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages real-time WebSocket (port 9999) + Moonraker HTTP API (port 7125) for all Creality printers."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        moonraker_port: int = DEFAULT_MOONRAKER_PORT,
        ws_port: int = DEFAULT_WS_PORT,
        camera_url: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.host = host
        self.moonraker_port = moonraker_port
        self.ws_port = ws_port
        self.camera_url = camera_url
        self.session = async_get_clientsession(hass)

        self.ws_data: dict[str, Any] = {}
        self.moonraker_data: dict[str, Any] = {}
        self.available_files: list[str] = []
        self.selected_preview_file: str | None = None
        self._thumbnail_cache: dict[str, bytes] = {}
        self.detected_cfs_units: list[str] = ["T1"]

        self._ws_task: asyncio.Task | None = None
        self._ws_client: aiohttp.ClientWebSocketResponse | None = None
        self._stop_ws = False

        # State tracking for firing Home Assistant notification events
        self._last_print_state: str | None = None
        self._last_layer: int | None = None
        self._last_errcode: int = 0
        self._last_filament_detected: bool = True

    @property
    def base_moonraker_url(self) -> str:
        """Return base URL for Moonraker."""
        return f"http://{self.host}:{self.moonraker_port}"

    @property
    def ws_url(self) -> str:
        """Return WebSocket URL for Creality native protocol."""
        return f"ws://{self.host}:{self.ws_port}"

    async def async_get_gcode_thumbnail(self, filename: str) -> bytes | None:
        """Extract the embedded 300x300 PNG thumbnail directly from the G-code file header."""
        if not filename or filename in ("Nenhum", "Nenhum ficheiro encontrado", "None"):
            return None

        if "/" in filename:
            filename = filename.rsplit("/", 1)[-1]

        if filename in self._thumbnail_cache:
            return self._thumbnail_cache[filename]

        # 1. Read the first 64 KB of the G-code file via HTTP Range request and decode embedded Base64 PNG
        file_url = f"{self.base_moonraker_url}/server/files/gcodes/{quote(filename)}"
        try:
            headers = {"Range": "bytes=0-65535"}
            async with self.session.get(file_url, headers=headers, timeout=6) as resp:
                if resp.status in (200, 206):
                    raw_bytes = await resp.read()
                    header_text = raw_bytes.decode("utf-8", errors="ignore")
                    matches = _THUMBNAIL_PATTERN.findall(header_text)
                    if matches:
                        best_match = max(
                            matches, key=lambda m: int(m[0]) * int(m[1])
                        )
                        b64_block = best_match[2]
                        b64_clean = "".join(
                            line.lstrip("; \t").strip()
                            for line in b64_block.splitlines()
                        )
                        img_bytes = base64.b64decode(b64_clean)
                        if img_bytes.startswith(b"\x89PNG") or img_bytes.startswith(b"\xff\xd8"):
                            self._thumbnail_cache[filename] = img_bytes
                            return img_bytes
        except Exception as err:
            _LOGGER.debug("Range header thumbnail extraction failed for %s: %s", filename, err)

        # 2. Fallback: Check standard Moonraker metadata thumbnails if present
        try:
            meta_url = (
                f"{self.base_moonraker_url}/server/files/metadata"
                f"?filename={quote(filename)}"
            )
            async with self.session.get(meta_url, timeout=4) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    thumbs = body.get("result", {}).get("thumbnails", [])
                    if thumbs:
                        best = max(
                            thumbs, key=lambda t: t.get("width", 0) * t.get("height", 0)
                        )
                        rel_path = best.get("relative_path")
                        if rel_path:
                            thumb_url = (
                                f"{self.base_moonraker_url}/server/files/gcodes/"
                                f"{quote(rel_path)}"
                            )
                            async with self.session.get(thumb_url, timeout=4) as t_resp:
                                if t_resp.status == 200:
                                    img_bytes = await t_resp.read()
                                    self._thumbnail_cache[filename] = img_bytes
                                    return img_bytes
        except Exception:
            pass

        return None

    async def async_start_websocket(self) -> None:
        """Start background WebSocket listener on port 9999."""
        self._stop_ws = False
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = self.hass.async_create_background_task(
                self._ws_loop(), f"{DOMAIN}_ws_{self.host}"
            )

    async def async_stop_websocket(self) -> None:
        """Stop background WebSocket listener."""
        self._stop_ws = True
        if self._ws_client and not self._ws_client.closed:
            await self._ws_client.close()
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()

    async def _ws_loop(self) -> None:
        """Maintain persistent connection to ws://<host>:9999 and push updates."""
        while not self._stop_ws:
            try:
                async with self.session.ws_connect(
                    self.ws_url, heartbeat=25, timeout=10
                ) as ws:
                    self._ws_client = ws
                    _LOGGER.info("Connected to Creality WebSocket at %s", self.ws_url)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                if isinstance(payload, dict):
                                    self.ws_data.update(payload)
                                    self._check_and_fire_events()
                                    self.async_set_updated_data(self._build_merged_data())
                            except json.JSONDecodeError:
                                continue
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.debug("WebSocket connection error on %s: %s", self.ws_url, err)

            self._ws_client = None
            if not self._stop_ws:
                await asyncio.sleep(5)

    async def async_send_ws_command(self, params: dict[str, Any]) -> bool:
        """Send a 'method: set' JSON command over port 9999 WebSocket."""
        payload = {"method": "set", "params": params}
        if self._ws_client and not self._ws_client.closed:
            try:
                await self._ws_client.send_json(payload)
                return True
            except Exception as err:
                _LOGGER.warning("Failed sending WS command via active socket: %s", err)

        try:
            async with self.session.ws_connect(self.ws_url, timeout=5) as ws:
                await ws.send_json(payload)
                return True
        except Exception as err:
            _LOGGER.error("Failed sending WS command to %s: %s", self.ws_url, err)
            return False

    async def async_send_gcode(self, script: str) -> bool:
        """Send G-code command via Moonraker HTTP API or WebSocket fallback."""
        url = f"{self.base_moonraker_url}/printer/gcode/script"
        try:
            async with self.session.post(
                url, json={"script": script}, timeout=10
            ) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        # Fallback: send gcodeCommand over native WebSocket 9999 (for K1 / Ender-3 V3 without Moonraker)
        return await self.async_send_ws_command({"gcodeCmd": script})

    async def async_moonraker_post(self, endpoint: str, data: dict[str, Any] | None = None) -> bool:
        """Call a Moonraker POST endpoint (e.g., /printer/print/pause)."""
        url = f"{self.base_moonraker_url}{endpoint}"
        try:
            async with self.session.post(url, json=data or {}, timeout=10) as resp:
                return resp.status == 200
        except Exception as err:
            _LOGGER.debug("Moonraker POST %s failed: %s", endpoint, err)
            return False

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll Moonraker HTTP API for CFS slots, detailed objects, and G-code files."""
        query_url = (
            f"{self.base_moonraker_url}/printer/objects/query"
            "?box&print_stats&virtual_sdcard&extruder&heater_bed"
            "&output_pin%20LED&output_pin%20fan0&output_pin%20fan1&output_pin%20fan2"
            "&fan_feedback&filament_switch_sensor%20filament_sensor"
            "&filament_switch_sensor%20filament_sensor_2&gcode_move"
            "&display_status&temperature_sensor%20mcu_temp&temperature_sensor%20chamber_temp"
        )
        try:
            async with self.session.get(query_url, timeout=8) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    self.moonraker_data = body.get("result", {}).get("status", {})
        except Exception as err:
            if not self.ws_data:
                # Try one quick WebSocket read if Moonraker is closed (e.g. stock K1 firmware)
                try:
                    async with self.session.ws_connect(self.ws_url, timeout=5) as ws:
                        msg = await ws.receive(timeout=4)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self.ws_data.update(json.loads(msg.data))
                except Exception as ws_err:
                    raise UpdateFailed(
                        f"Error communicating with printer {self.host}: {err} / {ws_err}"
                    ) from ws_err

        # Fetch available G-code files list periodically
        try:
            files_url = f"{self.base_moonraker_url}/server/files/list?root=gcodes"
            async with self.session.get(files_url, timeout=5) as f_resp:
                if f_resp.status == 200:
                    f_body = await f_resp.json()
                    files_list = f_body.get("result", [])
                    self.available_files = [
                        item["path"]
                        for item in sorted(
                            files_list,
                            key=lambda x: x.get("modified", 0),
                            reverse=True,
                        )[:50]
                        if "path" in item
                    ]
                    if not self.selected_preview_file and self.available_files:
                        self.selected_preview_file = self.available_files[0]
        except Exception:
            pass

        self._check_and_fire_events()
        return self._build_merged_data()

    def _check_and_fire_events(self) -> None:
        """Detect state transitions, layer changes, filament runout, and errors to fire HA events."""
        merged = self._build_merged_data()
        current_state = merged.get("status", "standby")
        current_layer = merged.get("current_layer", 0)
        err_code = merged.get("error_code", 0)
        filament_ok = merged.get("filament_detected", True)
        filename = merged.get("filename", "")

        # 1. Print State Transitions
        if self._last_print_state is not None and current_state != self._last_print_state:
            event_payload = {
                "host": self.host,
                "hostname": merged.get("hostname", self.host),
                "previous_state": self._last_print_state,
                "new_state": current_state,
                "filename": filename,
                "progress": merged.get("progress", 0),
                "current_layer": current_layer,
                "total_layers": merged.get("total_layers", 0),
                "Active_cfs_slot": merged.get("cfs_active_slot", "Nenhum"),
            }
            if current_state == "printing" and self._last_print_state != "paused":
                self.hass.bus.async_fire(EVENT_PRINT_STARTED, event_payload)
            elif current_state == "complete" or (
                self._last_print_state == "printing"
                and current_state == "standby"
                and merged.get("progress", 0) >= 99
            ):
                self.hass.bus.async_fire(EVENT_PRINT_FINISHED, event_payload)
            elif current_state == "paused":
                self.hass.bus.async_fire(EVENT_PRINT_PAUSED, event_payload)
            elif current_state in ("error", "cancelled"):
                self.hass.bus.async_fire(EVENT_PRINT_FAILED, event_payload)

        self._last_print_state = current_state

        # 2. Layer Change Event
        if (
            current_state == "printing"
            and current_layer
            and self._last_layer is not None
            and current_layer != self._last_layer
        ):
            self.hass.bus.async_fire(
                EVENT_LAYER_CHANGED,
                {
                    "host": self.host,
                    "filename": filename,
                    "current_layer": current_layer,
                    "total_layers": merged.get("total_layers", 0),
                    "progress": merged.get("progress", 0),
                },
            )
        if current_layer:
            self._last_layer = current_layer

        # 3. Filament Runout Event
        if self._last_filament_detected and not filament_ok:
            self.hass.bus.async_fire(
                EVENT_FILAMENT_RUNOUT,
                {
                    "host": self.host,
                    "filename": filename,
                    "active_slot": merged.get("cfs_active_slot", "Desconhecido"),
                },
            )
        self._last_filament_detected = filament_ok

        # 4. Printer Hardware Error Event
        if err_code != 0 and err_code != self._last_errcode:
            self.hass.bus.async_fire(
                EVENT_PRINTER_ERROR,
                {
                    "host": self.host,
                    "error_code": err_code,
                    "error_key": merged.get("error_key", 0),
                    "filename": filename,
                },
            )
        self._last_errcode = err_code

    def _build_merged_data(self) -> dict[str, Any]:
        """Combine Moonraker 7125 + Native WebSocket 9999 data into a unified dictionary."""
        mr = self.moonraker_data
        ws = self.ws_data

        extruder = mr.get("extruder", {})
        heater_bed = mr.get("heater_bed", {})
        print_stats = mr.get("print_stats", {})
        vsd = mr.get("virtual_sdcard", {})
        gcode_move = mr.get("gcode_move", {})
        box = mr.get("box", {})
        fan_fb = mr.get("fan_feedback", {})
        fil_sensor = mr.get("filament_switch_sensor filament_sensor", {})
        mcu_sensor = mr.get("temperature_sensor mcu_temp", {})
        chamber_sensor = mr.get("temperature_sensor chamber_temp", {})

        # Parse up to 4 CFS units (T1..T4 -> up to 16 slots T1A..T4D)
        same_mat_map: dict[str, str] = {}
        for entry in box.get("same_material", []):
            if isinstance(entry, list) and len(entry) >= 4:
                slots = entry[2] if isinstance(entry[2], list) else []
                mat_name = str(entry[3])
                for s in slots:
                    same_mat_map[str(s)] = mat_name

        cfs_slots: dict[str, dict[str, Any]] = {}
        active_units: list[str] = []

        for unit_id in ("T1", "T2", "T3", "T4"):
            unit_obj = box.get(unit_id, {})
            if not isinstance(unit_obj, dict):
                continue
            unit_connected = unit_obj.get("state") == "connect" or unit_id == "T1"
            if unit_connected:
                active_units.append(unit_id)

            colors = unit_obj.get("color_value", ["-1", "-1", "-1", "-1"])
            mat_codes = unit_obj.get("material_type", ["-1", "-1", "-1", "-1"])
            venders = unit_obj.get("vender", ["unknown", "unknown", "unknown", "unknown"])
            remains = unit_obj.get("remain_len", ["-1", "-1", "-1", "-1"])

            for idx, letter in enumerate(("A", "B", "C", "D")):
                slot_key = f"{unit_id}{letter}"
                raw_code = str(mat_codes[idx]) if idx < len(mat_codes) else "-1"
                raw_color = str(colors[idx]) if idx < len(colors) else "-1"
                mat_label = same_mat_map.get(
                    slot_key, CFS_MATERIAL_MAP.get(raw_code, raw_code)
                )
                hex_color = _parse_color_hex(raw_color)
                is_empty = raw_code in ("-1", "None", "")
                cfs_slots[slot_key] = {
                    "slot": slot_key,
                    "unit": unit_id,
                    "unit_connected": unit_obj.get("state") == "connect",
                    "material": "Vazio" if is_empty else mat_label,
                    "material_code": raw_code,
                    "color_hex": hex_color,
                    "vendor": str(venders[idx]) if idx < len(venders) else "unknown",
                    "remain_length": str(remains[idx]) if idx < len(remains) else "-1",
                    "loaded": box.get("extruder_last_tnn") == slot_key,
                    "empty": is_empty,
                }

        if active_units:
            self.detected_cfs_units = active_units

        t1 = box.get("T1", {}) if isinstance(box.get("T1"), dict) else {}

        # Filename cleanup
        raw_filename = print_stats.get("filename") or ws.get("printFileName") or ""
        if "/" in raw_filename:
            raw_filename = raw_filename.rsplit("/", 1)[-1]

        # Print progress
        ws_progress = ws.get("printProgress") or ws.get("dProgress")
        mr_progress = vsd.get("progress")
        if ws_progress is not None:
            progress = int(ws_progress)
        elif mr_progress is not None:
            progress = round(float(mr_progress) * 100, 1)
        else:
            progress = 0

        # Temperatures (Nozzle, Bed, Chamber, MCU)
        nozzle_temp = round(
            float(extruder.get("temperature") or ws.get("nozzleTemp") or 0.0), 1
        )
        nozzle_target = round(
            float(extruder.get("target") or ws.get("targetNozzleTemp") or 0.0), 1
        )
        bed_temp = round(
            float(heater_bed.get("temperature") or ws.get("bedTemp0") or 0.0), 1
        )
        bed_target = round(
            float(heater_bed.get("target") or ws.get("targetBedTemp0") or 0.0), 1
        )
        chamber_temp = round(
            float(
                chamber_sensor.get("temperature")
                or ws.get("boxTemp")
                or 0.0
            ),
            1,
        )

        # Light & Fans
        led_pin = mr.get("output_pin LED", {}).get("value")
        light_on = bool(led_pin) if led_pin is not None else bool(ws.get("lightSw", 0))

        model_fan_pct = int(
            ws.get(
                "modelFanPct",
                round(float(mr.get("output_pin fan0", {}).get("value", 0)) * 100),
            )
        )
        aux_fan_pct = int(
            ws.get(
                "auxiliaryFanPct",
                round(float(mr.get("output_pin fan2", {}).get("value", 0)) * 100),
            )
        )
        case_fan_pct = int(
            ws.get(
                "caseFanPct",
                round(float(mr.get("output_pin fan1", {}).get("value", 0)) * 100),
            )
        )

        err_obj = ws.get("err", {}) if isinstance(ws.get("err"), dict) else {}

        # Status normalization across Klipper & native WebSocket
        ws_state = ws.get("state")
        ws_status_map = {
            0: "standby",
            1: "printing",
            2: "complete",
            3: "failed",
            4: "cancelled",
            5: "paused",
        }
        status = print_stats.get("state") or ws_status_map.get(ws_state, "standby")

        return {
            "hostname": ws.get("hostname") or self.host,
            "model": ws.get("model", "Creality 3D Printer"),
            "sw_version": ws.get("modelVersion", "Creality OS / Klipper"),
            "status": status,
            "filename": raw_filename,
            "selected_preview_file": self.selected_preview_file or raw_filename,
            "progress": progress,
            "current_layer": int(ws.get("layer") or 0),
            "total_layers": int(
                ws.get("TotalLayer")
                or vsd.get("file_metadata", {}).get("layer_count")
                or 0
            ),
            "print_job_time_s": int(ws.get("printJobTime") or print_stats.get("print_duration") or 0),
            "print_left_time_s": int(ws.get("printLeftTime") or 0),
            "nozzle_temp": nozzle_temp,
            "nozzle_target": nozzle_target,
            "bed_temp": bed_temp,
            "bed_target": bed_target,
            "chamber_temp": chamber_temp,
            "mcu_temp": round(float(mcu_sensor.get("temperature") or 0.0), 1),
            "box_temp": float(t1.get("temperature") if t1.get("temperature") not in (None, "None", "-1") else ws.get("boxTemp", 0)),
            "box_humidity": float(t1.get("dry_and_humidity") if t1.get("dry_and_humidity") not in (None, "None", "-1") else 0),
            "realtime_speed_mms": round(float(ws.get("realTimeSpeed") or 0.0), 1),
            "realtime_flow_mm3s": round(float(ws.get("realTimeFlow") or 0.0), 2),
            "feedrate_pct": int(
                ws.get("curFeedratePct")
                or round(float(gcode_move.get("speed_factor", 1.0)) * 100)
            ),
            "flowrate_pct": int(
                ws.get("curFlowratePct")
                or round(float(gcode_move.get("extrude_factor", 1.0)) * 100)
            ),
            "speed_mode": int(ws.get("speedMode", 0)),
            "ai_detection": bool(ws.get("aiDetection", 0) or ws.get("aiSw", 0)),
            "position": ws.get("curPosition", "X:0 Y:0 Z:0"),
            "used_material_mm": round(
                float(print_stats.get("filament_used") or ws.get("usedMaterialLength") or 0.0),
                1,
            ),
            "light_on": light_on,
            "model_fan_pct": model_fan_pct,
            "aux_fan_pct": aux_fan_pct,
            "case_fan_pct": case_fan_pct,
            "fan0_rpm": int(fan_fb.get("fan0_speed", 0)),
            "filament_detected": bool(fil_sensor.get("filament_detected", not bool(ws.get("materialDetect", 0)))),
            "cfs_connected": box.get("state") == "connect" or bool(ws.get("cfsConnect", 0)),
            "cfs_type": box.get("type", "CFS"),
            "cfs_active_slot": box.get("extruder_last_tnn", "Nenhum"),
            "cfs_auto_refill": bool(box.get("auto_refill", 0)),
            "cfs_slots": cfs_slots,
            "error_code": int(err_obj.get("errcode", 0)),
            "error_key": int(err_obj.get("key", 0)),
            "available_files": self.available_files,
        }
