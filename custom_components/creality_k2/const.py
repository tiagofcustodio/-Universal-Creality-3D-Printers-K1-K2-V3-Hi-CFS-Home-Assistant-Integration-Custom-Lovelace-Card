"""Constants and model mappings for the Universal Creality Klipper / K-Series integration."""

DOMAIN = "creality_k2"

CONF_HOST = "host"
CONF_MOONRAKER_PORT = "moonraker_port"
CONF_WS_PORT = "ws_port"
CONF_CAMERA_URL = "camera_url"

DEFAULT_MOONRAKER_PORT = 7125
DEFAULT_WS_PORT = 9999
DEFAULT_SCAN_INTERVAL = 5

# Events fired by the integration for automations & notifications
EVENT_PRINT_STARTED = f"{DOMAIN}_print_started"
EVENT_PRINT_FINISHED = f"{DOMAIN}_print_finished"
EVENT_PRINT_FAILED = f"{DOMAIN}_print_failed"
EVENT_PRINT_PAUSED = f"{DOMAIN}_print_paused"
EVENT_LAYER_CHANGED = f"{DOMAIN}_layer_changed"
EVENT_FILAMENT_RUNOUT = f"{DOMAIN}_filament_runout"
EVENT_PRINTER_ERROR = f"{DOMAIN}_printer_error"

# Services
SERVICE_SEND_GCODE = "send_gcode"
SERVICE_START_PRINT = "start_print"
SERVICE_CFS_LOAD = "cfs_load_slot"
SERVICE_CFS_UNLOAD = "cfs_unload"
SERVICE_CFS_REFRESH = "cfs_refresh"

# Known Creality Internal Model Codes -> Friendly Marketing Names
CREALITY_MODEL_MAP = {
    "F001": "Creality K1",
    "F002": "Creality K1 Max",
    "F004": "Creality K1C",
    "F005": "Creality K1 SE",
    "F008": "Creality K2 Plus",
    "F012": "Creality K2 Pro",
    "F016": "Creality K2 SE",
    "F021": "Creality Ender-3 V3",
    "F022": "Creality Ender-3 V3 Plus",
    "F023": "Creality Ender-3 V3 KE",
    "F025": "Creality Hi",
}

# Known Creality CFS RFID Material Codes
CFS_MATERIAL_MAP = {
    "00001": "PLA",
    "00002": "ABS",
    "00003": "PETG",
    "00004": "TPU",
    "00005": "PA (Nylon)",
    "00006": "ASA",
    "00007": "PC",
    "00008": "PLA-CF",
    "00009": "PA-CF",
    "00010": "PET-CF",
    "006001": "PETG",
    "01001": "Hyper PLA",
    "01002": "Hyper PLA-CF",
    "02001": "Hyper ABS",
    "03001": "Hyper PETG",
    "04001": "CR-PLA",
    "06001": "CR-PETG",
    "07001": "CR-ABS",
    "09001": "CR-Silk",
    "-1": "Empty",
    "None": "Empty",
}

SPEED_MODES = {
    0: "Normal (100%)",
    1: "Silent (Quiet)",
    2: "Sport (125%)",
    3: " Ludicrous (160%)",
}
