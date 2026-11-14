# AGENTS.md — The Lighthouse Companion (Arduino UNO Q)

This file serves as the single source of truth for AI coding agents (OpenCode / BigPickle, Cursor, Claude Code, etc.) working on **The Lighthouse Companion** repository. Always adhere to the hardware constraints, architectural boundaries, and UX rules defined below.

---

## 1. Project Overview & Hackathon Philosophy

- **Challenge:** *"Make Europe Green through Edge AI using Arduino"* (The Green European Renaissance).
- **Product Vision:** **The Lighthouse Companion** is a single, standalone Edge AI "Master Botanist" device that guides complete beginners and elderly users through the entire lifecycle of their personal tiny garden (balcony, patio, or windowsill) so they can grow **self-sustaining companion plants** with zero prior gardening knowledge.
- **Core Anti-Megacorp / Solarpunk Principles:**
  1. **One Device for the Whole Balcony:** Never require per-pot electronic sensors or batteries (which create e-waste). One elevated "Lighthouse" unit overlooks the entire balcony/space.
  2. **100% Offline & App-Free:** Zero cloud dependencies, zero smartphone apps, zero subscriptions. All AI inference, spatial mapping, and plant recommendations run locally on the device.
  3. **Elderly & Novice Accessible:** High-contrast 4.3"–5.0" matte screen (18pt–24pt fonts, cream background, dark text), tactile navigation via a single wooden rotary encoder knob, and zero botanical jargon.

---

## 2. Target Hardware & Bill of Materials (BOM)

1. **Compute Platform:** **Arduino UNO Q** (Heterogeneous Dual-Processor Board)
   - **Brain 1 (Real-Time MCU):** STM32U585 microcontroller (runs Arduino C++ sketch, reads I2C/GPIO, drives the onboard **8x13 blue LED matrix**).
   - **Brain 2 (Edge AI & Vision MPU):** Qualcomm Dragonwing QRB2210 running Debian Linux + Python 3 (runs OpenCV, MiDaS ONNX depth estimation, Sunlight Heatmap math, and the PyGame Kiosk UI).
2. **Vision Sensor:** **Arduino USB Camera (`TPX00246`)**
   - Full HD (1920x1080) / 8MP Sony IMX376 sensor, 80° diagonal FOV, F/2.0 autofocus lens, built-in microphone, physical privacy shutter, and 4000 Lux LED ring light.
   - *Crucial Hardware Rule:* Always capture at `1280x720` or `640x480` in OpenCV to keep frame rates high, and lock manual exposure (`v4l2-ctl -d /dev/video0 -c auto_exposure=1 -c exposure_time_absolute=150`) during sunlight scanning so auto-exposure doesn't artificially brighten dark corners.
3. **Climate Sensor:** **Adafruit BME280** or **Sensirion SHT4x** connected via Qwiic / I2C (`0x76`) to the STM32 MCU.
4. **User Input:** **Rotary Encoder with Push-Button** (`CLK=D2`, `DT=D3`, `SW=D4` on STM32) + keyboard fallback (`LEFT`, `RIGHT`, `RETURN`) for desktop/laptop testing.
5. **Passive Physical Accessories:**
   - **4 cm × 4 cm ArUco Wooden Stakes (`DICT_4X4_50`):** Stuck into existing empty pots (`Tag #1`, `Tag #2`, `Tag #3`) or placed on an empty floor (`Tag #0` scale anchor).
   - **Biodegradable Cardboard Seed Stencils:** Pre-punched with holes `A`, `B`, and `C` so beginners can plant companion trios with foolproof spacing.

---

## 3. Repository Structure

~~~text
lighthouse_companion/
├── AGENTS.md                        # This architecture & agent instruction file
├── setup_env.sh                     # Installs pip packages, downloads MiDaS ONNX, builds ArUco sheet
├── mcu_firmware/
│   └── mcu_firmware.ino             # STM32U585 C++ sketch (BME280, Rotary Knob, 8x13 LED Matrix, Serial/RPC)
└── linux_app/
    ├── requirements.txt             # opencv-contrib-python, numpy, pygame, pyserial
    ├── guilds_db.json               # Offline European Companion Plant Trios database
    ├── spatial_vision.py            # Phase 1 Vision: ArUco Pinhole Math + MiDaS 3D Depth + K-Means + Sun Map
    ├── plant_monitor.py             # Phase 2 Vision: Canopy Cover %, Height (cm), Yellowing, VPD + Soil Thirst
    ├── main_kiosk.py                # 800x480 Senior-Friendly PyGame UI & 4-State Orchestrator
    └── generate_aruco_stakes.py     # Generates printable 4cm x 4cm ArUco markers sheet
~~~

---

## 4. Technical Architecture & Core Algorithms

### Phase 1: The 24-Hour Setup & Spatial Mapper (`spatial_vision.py`)
1. **First-Boot Handshake (Automatic Mode Detection):**
   - On startup, the camera takes a baseline frame (`1280x720`) and runs OpenCV ArUco detection (`cv2.aruco.DICT_4X4_50`).
   - **Branch A (`EXISTING_POTS` — Method 2 Pinhole Math):** If pot tags (`ID >= 1`) are detected, calculate the exact distance to each pot and scale the pot diameter in centimeters using calibrated pinhole geometry ($F_{px} = 880.0$ at `1280x720`, $W_{\text{tag}} = 4.0\text{ cm}$):
     - `distance_cm = (4.0 * 880.0) / tag_px_width`
     - `pot_diameter_cm = (pot_px_width / tag_px_width) * 4.0`
   - **Branch B (`EMPTY_BALCONY` — Method 1 Monocular Depth AI + Adaptive K-Means):** If no pot tags are present, run **`MiDaS v2.1 Small` (`model-small.onnx`)** via `cv2.dnn`.
     - **Sky/Street Filtering:** Discard the bottom 15th percentile of inverse depth values (`np.percentile(depth_raw, 15)`) so distant buildings and sky outside the balcony are ignored.
     - **Scale-Invariant Clustering:** Run **1D K-Means ($K=3$)** on valid balcony pixels to dynamically segment the space into `Zone A (Near Foreground)`, `Zone B (Mid Balcony)`, and `Zone C (Far Railing)` regardless of balcony dimensions.
     - **Hybrid Anchor (`Tag #0`):** If `Tag #0` is lying on the empty balcony floor, use its pinhole distance to calibrate all three K-Means depth zones into real-world centimeters.
2. **24-Hour Sunlight Heatmap Accumulator:**
   - Samples frames over 24 hours (or 10 fast-forward ticks in **Hackathon Demo Mode**), thresholds sunlit grayscale pixels (`> 175`), and accumulates them into a 2D NumPy array (`sun_accumulator`) to compute exact daily sun hours (`0.0` to `10.0` hours) per pot bounding box or 3D K-Means surface mask.
3. **Companion Guild Matching (`guilds_db.json`):**
   - Matches each spot's `[sun_hours, avg_temp_c]` to self-sustaining European plant trios (e.g., *Dwarf Tomato + Genovese Basil + French Marigold* for sunny spots; *Oakleaf Lettuce + Chives + Wild Strawberry* for half-shade).

### Phase 2: Non-Contact Optical Phenotyping & Care (`plant_monitor.py`)
Uses the **exact same camera and climate sensor** (zero soil electronics) to monitor growing plants across all pots:
1. **Biomass & Real Height in cm:** Converts each pot's bounding box to HSV, isolates green foliage (`Hue 35–85`), computes `canopy_pct`, and scales the vertical pixel height of the plant contour against the 4 cm ArUco stake (`height_cm = (plant_px_h / tag_px_h) * 4.0`).
2. **Leaf Stress / Chlorosis Detection:** Computes the ratio of yellowing pixels (`Hue 15–34`) to healthy green pixels to warn if a pot needs shade or nutrients.
3. **Non-Contact Thirst Index (VPD + Topsoil Luminance):**
   - Calculates atmospheric **Vapor Pressure Deficit ($VPD$ in kPa)** from the STM32's temperature and humidity readings:
     - $SVP = 0.61078 \times \exp\left(\frac{17.27 \times T}{T + 237.3}\right)$
     - $VPD = SVP \times \left(1 - \frac{RH}{100}\right)$
   - Combines $VPD$, daily sun hours, and the HSV Value (brightness) of non-green topsoil pixels (dry soil is bright/light; wet soil is dark) into a unified `thirst_index` (`needs_water = thirst_index > 0.58`).

---

## 5. Inter-Processor Protocol (STM32 <-> Linux Serial/RPC)

The STM32 (`mcu_firmware.ino`) and Linux Python app (`main_kiosk.py`) communicate over `/dev/ttyACM*` at `115200` baud using plain-text newline-delimited messages:

- **STM32 -> Linux:**
  - `EVENT:KNOB_RIGHT` / `EVENT:KNOB_LEFT` — Cycles through detected pots or 3D balcony zones.
  - `EVENT:CLICK` — Advances the UI state machine (`BOOT_CONFIRM` -> `SCANNING` -> `PHASE1_PLAN` -> `PHASE2_CARE`).
  - `EVENT:LONG_PRESS_DEMO` — Triggers the 10-second fast-forward scan for live hackathon judging.
  - `CLIMATE:<temp_c>,<hum_pct>` — Pushed every 2 seconds (e.g., `CLIMATE:22.8,54.2`).
- **Linux -> STM32:**
  - `ZONE:<idx>` — Lights up the corresponding spatial columns on the onboard 8x13 LED matrix.
  - `PROG:<cols>` — Renders a 0–13 column progress bar on the 8x13 LED matrix during scanning.

---

## 6. Coding Conventions & Guardrails for AI Agents

1. **Graceful Hardware Fallbacks:** The Python application (`main_kiosk.py`) MUST always run cleanly on a standard developer laptop even if `/dev/ttyACM0` (STM32), `model-small.onnx` (MiDaS), or an external webcam is disconnected. Always keep the keyboard controls (`LEFT`, `RIGHT`, `RETURN`) and synthetic frame fallbacks intact.
2. **Senior-Friendly UI Rules:** Never shrink font sizes below `20px` in `main_kiosk.py`. Maintain the high-contrast warm cream background (`#F8F4E8`) and dark text (`#141414`), and keep strings free of raw technical jargon.
3. **Verification Commands:** Whenever modifying Python files in `linux_app/`, always run:
   ~~~bash
   python3 -m py_compile lighthouse_companion/linux_app/*.py
   ~~~