# 🖨️ Universal Creality 3D Printers for Home Assistant (`creality_k2`)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

Complete **Local Push** Home Assistant custom integration + **All-in-One Custom Lovelace Card** (`custom:creality-k2-card`) for **all Creality Klipper / Creality OS 3D Printers** and the **CFS (Creality Filament System)**.

Combines both local protocols simultaneously with **zero cloud dependency**:
- **Native Creality WebSocket (`ws://<IP>:9999`)**: Instant real-time push updates (`local_push`) for layer progress, speed, volumetric flow, remaining time, coordinates, LED light, and fans (works even on stock non-rooted firmware).
- **Moonraker / Klipper HTTP API (`http://<IP>:7125`)**: Deep integration with **Creality CFS (4 to 16 colors)**, RFID filament materials & hex colors, stored `.gcode` file management, direct Base64 `300x300` 3D thumbnail extraction, and G-Code macro execution.

---

## ✅ Supported Creality Printers

| Series | Models Supported |
| :--- | :--- |
| **Creality K2 Series** | **K2 SE**, **K2 Pro**, **K2 Plus** (including 4C / 8C / 16C CFS Combos) |
| **Creality K1 Series** | **K1**, **K1C**, **K1 Max**, **K1 SE** |
| **Creality Ender-3 V3** | **Ender-3 V3**, **Ender-3 V3 Plus**, **Ender-3 V3 KE** |
| **Creality Hi Series** | **Creality Hi** & **Creality Hi Combo (CFS)** |
| **Multi-Color System** | **CFS** & **CFS-Nano** (1 to 4 units — up to 16 filament slots `T1A`–`T4D`) |

---

## ✨ Key Features

1. **🎨 Built-in Custom Lovelace Card (`custom:creality-k2-card`)**
   - Automatically registered into Home Assistant's frontend — **no separate HACS frontend installation required!**
   - **Responsive Design** tailored for Smartphones, Tablets, and Desktop dashboards (inspired by *Creality Print*).
   - **Live XY & Z Jog D-Pad** with selectable step (`0.1mm`, `1mm`, `10mm`, `100mm`), real-time `X / Y / Z` coordinates, and Home buttons.
   - **4 Hardware Control Sub-Cards**: Model Fan, Back/Exhaust Fan, Side/Auxiliary Fan, and Enclosure LED Light.
   - **Interactive CFS Spool Rack**: Displays real filament colors (`#RRGGBB`), material type (`PLA`, `PETG`, `ABS`, `TPU`, `ASA`, `PA-CF`, etc.), active extruder slot, and 1-tap spool loading.
   - **Instant 3D File Preview & Launcher**: Browse `.gcode` files stored on the printer and **instantly preview the embedded `300x300` 3D model image** before starting the print.
2. **🔔 Native Events & Ready-to-Use Mobile Notification Blueprint**
   - Fires Home Assistant bus events (`creality_k2_print_started`, `creality_k2_print_finished`, `creality_k2_print_paused`, `creality_k2_print_failed`, `creality_k2_filament_runout`, `creality_k2_printer_error`, `creality_k2_layer_changed`).
   - Includes a ready-to-import **Automation Blueprint** that sends mobile push notifications with the 3D model/camera snapshot attached.

---

## 🚀 Installation (PT / EN)

### Option 1: Via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the **3 dots (`⋮`)** in the top-right corner and select **Custom repositories**.
3. Paste the URL of this GitHub repository and select category **Integration**.
4. Click **Download** on **Creality 3D Printers (K1 / K2 / Ender-3 V3 / Hi + CFS)**.
5. **Restart Home Assistant**.
6. Go to **Settings -> Devices & Services -> Add Integration** and search for **Creality**.
7. Enter your printer's local IP address (e.g., `192.168.1.79`) and click **Submit**.

### Option 2: Manual Installation
1. Copy the `custom_components/creality_k2` folder into your Home Assistant's `/config/custom_components/` directory.
2. *(Optional)* Copy `blueprints/automation/creality_k2/creality_k2_notifications.yaml` into `/config/blueprints/automation/creality_k2/`.
3. Restart Home Assistant and add the integration via **Settings -> Devices & Services -> Add Integration**.

---

## 📱 Adding the Custom Card to Your Dashboard

The custom card is automatically injected by the integration! Simply add a **Manual** card to any dashboard with **1 single line**:

```yaml
type: custom:creality-k2-card
```

*(Optional: If you have multiple Creality printers on your network, you can filter a card to a specific printer by adding `prefix: your_printer_slug`).*

---

## 🛠️ Custom Services Available

| Service | Description |
| :--- | :--- |
| `creality_k2.send_gcode` | Send any G-Code command or Klipper macro (`G28`, `M106 S255`, `BOX_INFO_REFRESH`). |
| `creality_k2.start_print` | Start printing a `.gcode` file stored on the printer's internal storage. |
| `creality_k2.cfs_load_slot` | Load/switch filament from a specific CFS slot (`T1A`, `T1B`, `T1C`, `T1D`, etc.). |
| `creality_k2.cfs_unload` | Cut and retract the active filament back into the CFS (`BOX_QUIT_MATERIAL`). |
| `creality_k2.cfs_refresh` | Refresh RFID & optical sensors across all CFS slots (`BOX_INFO_REFRESH`). |

---

## 📄 License
Distributed under the [GNU General Public License v3.0 (GPLv3)](LICENSE). Any modifications or derivative works must remain open-source under the same license and preserve original author attribution.
