# SPECTRA // IR-CORE
### Precision Windows Hello Infrared Studio & Virtual Webcam Suite

[![Windows](https://img.shields.io/badge/OS-Windows%2010%20%7C%2011-0078D4?logo=windows&logoColor=white)](https://microsoft.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![WinRT](https://img.shields.io/badge/WinRT-Direct%20Sensor%20Stream-FFB900)](https://github.com/microsoft/xlang)

---

**SPECTRA // IR-CORE** unlocks the hidden potential of your laptop's integrated Windows Hello Infrared (IR) camera sensor (typically used exclusively for biometric facial login). 

By capturing raw infrared data via the Windows MediaCapture WinRT API, **SPECTRA** provides a full cyber-tactical desktop studio with real-time optical controls, adaptive night-vision algorithms, thermal false-color palettes, and a system-wide virtual webcam driver for **Discord**, **Zoom**, **Google Meet**, **Microsoft Teams**, and **OBS**.

---

## ⚡ Highlights

- 🎛️ **Cyber-Tactical Studio App**: Native frameless desktop app with real-time luminance histogram, optical reticles, rule-of-thirds grid, and live telemetry log terminal.
- 🌙 **Adaptive Night Vision (CLAHE)**: Contrast Limited Adaptive Histogram Equalization with real-time clip limit and tile grid controls to see in pitch-black environments.
- 🎨 **7 Spectral Colormap Presets**:
  - **NVG Phosphor Green**: Tactical Military P43 night-vision phosphor simulation.
  - **Cyber Ice Blue**: High-contrast tactical cold palette.
  - **FLIR Inferno & Magma**: Thermal-style false-color heatmapping.
  - **Turbo Heat**: High-dynamic rainbow spectrum.
  - **Bone & Pure Mono**: Clean calibrated scientific infrared monochrome.
- 📹 **System-Wide Virtual Webcam**: Stream enhanced infrared footage directly into **Discord**, **Zoom**, **Meet**, **Teams**, and **Chrome** via `OBS Virtual Camera`.
- ⚡ **IR Flood LED Re-igniter (`[R]`)**: One-touch hardware watchdog reset that instantly re-activates the 850nm/940nm active IR flood illuminator when firmware sleep timers kick in.
- 📸 **Snapshot Archive**: Real-time high-resolution frame captures with flash feedback and in-app gallery preview.
- 🚀 **100% Portable**: Zero hardcoded paths, automatic virtual environment builder, silent windowless launcher, and 1-click desktop shortcut creator.

---

## 📋 Prerequisites

1. **Hardware**: Windows PC/laptop with a built-in or USB **Windows Hello Infrared (IR) Camera** (e.g., ThinkPad, Surface, Dell XPS, HP Spectre, ASUS ZenBook).
2. **Operating System**: Windows 10 or Windows 11 (64-bit).
3. **Python**: **Python 3.10** or **Python 3.11** (64-bit) recommended.
   > [!IMPORTANT]
   > The Windows Runtime SDK (`winsdk`) provides pre-compiled binary wheels for **Python 3.10 and 3.11**. If using Python 3.12+, you will need Microsoft C++ Build Tools installed.
4. **Virtual Camera (Optional)**: [OBS Studio](https://obsproject.com/) (provides the `OBS Virtual Camera` directshow driver used for broadcasting to Discord/Zoom).

---

## 🚀 Quick Start (1-Click Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/IR_Camera.git
cd IR_Camera
```

### 2. Run Automatic Setup
Double-click **`install.bat`** (or execute from terminal):
```cmd
install.bat
```
This script will:
- Detect your Python 3.10/3.11 installation.
- Create an isolated virtual environment (`.\venv`).
- Upgrade `pip` and install all required dependencies from `requirements.txt`.
- Optionally create a **`SPECTRA IR Camera Studio`** shortcut on your Desktop.

### 3. Launch
Choose any of the streamlined launchers:

| Launcher | Description |
|---|---|
| **`launch_app.vbs`** | **Primary silent launcher**: Launches the Studio directly with zero black command prompt / terminal windows. |
| **`run_studio_app.bat`** | Launches the Studio in an interactive terminal window with full logging output. |
| **`run_ir_viewer.bat`** | Lightweight, ultra-fast OpenCV standalone window viewer (no web browser required). |
| **`run_ir_virtual_cam.bat`** | Headless direct bridge streaming IR video directly to OBS Virtual Camera. |

---

## 🎮 Keyboard Shortcuts

### In the Primary Studio App:
| Key | Action |
|---|---|
| **`[R]`** | **Re-ignite IR Flood LED**: 0.3s hardware reset to re-energize active flood illumination. |
| **`[V]`** | **Toggle Virtual Camera**: Stream on/off to OBS Virtual Camera (Discord/Zoom). |
| **`[Space]`** | **Snapshot**: Capture high-res frame with shutter flash animation. |
| **`[G]`** | **Toggle Grid**: Show / hide optical reticles and rule-of-thirds grid. |
| **`[T]`** | **Toggle Telemetry**: Expand / collapse real-time terminal sensor logs. |

### In the OpenCV Viewer (`run_ir_viewer.bat`):
| Key | Action |
|---|---|
| **`[Space]` / `[M]` / `[Tab]`** | Cycle mode: Raw IR ↔ Night Vision (CLAHE) ↔ Thermal (Inferno) |
| **`[S]`** | Save high-resolution snapshot to `Captures/` |
| **`[R]`** | Re-ignite IR Flood LED |
| **`[H]`** | Toggle HUD overlay |
| **`[Q]` / `[Esc]`** | Exit viewer |

---

## 💡 Why Does the IR Flood Illuminator Turn Off?

The infrared flood illuminator (typically 850nm or 940nm LEDs) on Windows Hello cameras is engineered primarily for brief 2-to-3 second facial authentication scans:

1. **Eye Safety & Thermal Watchdog (IEC 62471 Class 1)**: Camera ISP firmware enforces an eye safety duty-cycle timeout. If continuous video streaming is detected, the firmware turns off the active flood LED to prevent thermal buildup and optical exposure, transitioning to passive infrared mode.
2. **Auto-Exposure / Ambient Light (AGC)**: If the sensor detects bright ambient light or a bright monitor reflection, auto-exposure cuts power to the LED to prevent sensor saturation.
3. **How SPECTRA Fixes This**: Tap **`[R]`** at any time. SPECTRA performs an instant 0.3-second session reset on the `MediaCapture` pipeline. This refreshes the camera firmware's watchdog timer and re-energizes the active flood illuminator immediately.

---

## 🛠️ Advanced CLI Options

You can pass command-line arguments to `app_server.py`:

```cmd
python app_server.py --help

options:
  -h, --help    Show help message and exit
  --port PORT   HTTP server port (default: 8765)
  --host HOST   HTTP server host (default: 127.0.0.1)
  --no-browser  Start headless server without opening browser window
```

---

## 📂 Project Architecture

```
IR_Camera/
├── Captures/                  # Auto-created snapshot storage (.gitignore protected)
│   └── .gitkeep
├── static/
│   └── index.html             # Self-contained cyber-tactical Web Studio UI
├── .gitignore                 # Pre-configured git exclusions
├── LICENSE                    # MIT License
├── README.md                  # Documentation
├── app_server.py              # WinRT sensor pipeline & MJPEG / REST studio server
├── create_desktop_shortcut.bat# Automated desktop shortcut generator
├── install.bat                # 1-click venv builder & dependency installer
├── ir_camera_viewer.py        # Lightweight standalone OpenCV viewer
├── ir_to_virtualcam.py        # Dedicated OBS Virtual Camera streaming bridge
├── launch_app.vbs             # Silent windowless desktop launcher
├── requirements.txt           # Python dependency specification
├── run_ir_viewer.bat          # Smart runner for standalone viewer
├── run_ir_virtual_cam.bat     # Smart runner for virtual cam bridge
└── run_studio_app.bat         # Smart runner for primary studio app
```

---

## 🔧 Troubleshooting

- **`winsdk` fails to install**: Make sure you are using Python 3.10 or Python 3.11. Python 3.12+ does not currently have pre-built wheels for `winsdk` on PyPI.
- **"Windows Hello IR camera not detected"**:
  1. Confirm your device has an IR camera (usually visible as two lenses at the top of your screen, one emitting a faint red/invisible pulse during Windows Hello).
  2. Open **Windows Settings > Privacy & Security > Camera** and ensure **"Let apps access your camera"** is toggled **ON**.
- **Virtual Camera not appearing in Discord / Zoom**: Install [OBS Studio](https://obsproject.com/) once to register the virtual camera system driver.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
