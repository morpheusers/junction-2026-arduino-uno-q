# The Lighthouse Companion — Arduino UNO Q

A smart balcony-gardening kiosk. It maps your balcony in 3D, measures real sunlight
hours and climate, recommends a compatible plant guild, then monitors your pots'
health and watering needs.

- **MCU firmware** (`mcu_firmware/mcu_firmware.ino`) — Modulino Knob, Thermo, and Buzzer, power button, LED-matrix feedback, serial bridge.
- **Linux kiosk app** (`linux_app/`) — USB camera capture, ArUco stake measurement, MiDaS monocular depth, plant-guild recommendation, optical plant care.

---

## 1. Hardware

| Item | Notes |
| --- | --- |
| Arduino UNO Q | STM32U585 MCU + QRB2210 Linux MPU |
| TPX00246 USB camera | 80° FOV, run at 1280×720 |
| Modulino Knob | Qwiic I²C — rotation + push-to-click |
| Modulino Thermo | Qwiic I²C — temperature and relative humidity |
| Modulino Buzzer | Qwiic I²C — watering alarm |
| Power button | Momentary switch between **D8** and **GND** (internal pull-up) |
| Printed ArUco stakes | `linux_app/printable_4cm_aruco_stakes.png`, printed at exactly **4 cm** square |

**Wiring:** daisy-chain the three Modulinos with Qwiic cables to the UNO Q Qwiic
port (the firmware initializes them over `Wire1`). Wire the power button between
**D8** and **GND** — no external resistor needed. D8 is a free GPIO (PB4 /
TIM3_CH1) and does not conflict with UART, SPI, or I²C.

The firmware falls back to `22.5 °C / 55 %` if the Thermo module is missing, and
reports `WARN:*_MISSING` lines on the serial port for any module it cannot find.

---

## 2. Print the ArUco stakes

The setup script generates the sheet automatically, or run it directly:

```bash
python3 lighthouse_companion/linux_app/generate_aruco_stakes.py
```

Print `lighthouse_companion/linux_app/printable_4cm_aruco_stakes.png` at 100 % scale
(no "fit to page") and verify the black marker square measures 4 cm. Glue
**Stake #1–#3** to three pots. **Tag #0** is an optional anchor — place it on the
floor or railing to get absolute centimetre distances on an empty balcony.

---

## 3. Flash the MCU firmware

1. Install the **Arduino UNO Q** board support in Arduino IDE / Arduino App Lab.
2. Install libraries **`Arduino_Modulino`** and **`Arduino_LED_Matrix`** via Library Manager.
3. Open `lighthouse_companion/mcu_firmware/mcu_firmware.ino`.
4. Select the Arduino UNO Q board and upload.
5. Open Serial Monitor at **115200 baud** to confirm the board is alive: you should
   see `CLIMATE:<temp>,<humidity>` every 2 seconds once connected.

---

## 4. Install the Linux / kiosk app

### On the UNO Q (target device)

```bash
cd <repo-root>
chmod +x lighthouse_companion/setup_env.sh
./lighthouse_companion/setup_env.sh
```

The script:
1. installs `opencv-contrib-python`, `numpy`, `pygame`, `pyserial`;
2. downloads the MiDaS v2.1 Small ONNX model (uses `wget` on Linux, `curl` on macOS);
3. generates the printable ArUco stake sheet.

MiDaS is optional — without it the app falls back to a synthetic perspective depth
map.

### On macOS (development / rehearsal)

Homebrew Python is externally managed, so use a virtualenv:

```bash
cd lighthouse_companion
python3 -m venv .venv
source .venv/bin/activate
pip install -r linux_app/requirements.txt
python linux_app/generate_aruco_stakes.py
```

Optional — fetch the MiDaS depth model:

```bash
curl -L --fail -o linux_app/model-small.onnx \
  https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx
```

> On macOS, `v4l2-ctl` is unavailable, so camera-exposure locking is silently
> skipped. This is expected and harmless.

---

## 5. Start the kiosk

```bash
cd lighthouse_companion/linux_app
python3 main_kiosk.py
```

The app opens an **800×480** window titled *The Lighthouse Companion - UNO Q* and
uses camera index `0` (the TPX00246 USB camera, normally `/dev/video0`).

### State flow

1. **BOOT_CONFIRM** — camera preview with detected spots. Shows either
   `FOUND N EMPTY POTS` (ArUco stakes seen) or `EMPTY BALCONY DETECTED`
   (3 depth zones mapped by MiDaS/k-means).
2. **SCANNING** — 10 sample frames (about 4 seconds) accumulate sunlight.
   Shine a flashlight on a pot/zone to simulate hours of sun.
3. **PHASE1_PLAN** — per-spot guild recommendation with plant list and stencil guide.
4. **PHASE2_CARE** — live plant health: watering advice, height, canopy %, VPD.
5. Click the knob again on **PHASE2_CARE** to re-scan the balcony and restart.

### Controls

| Input | Action |
| --- | --- |
| Rotate knob right / `→` | Select next spot / zone |
| Rotate knob left / `←` | Select previous spot / zone |
| Click knob / `Enter` | Advance to the next phase |
| Long-press knob (1.5 s) | Demo shortcut — advances phase |
| Power button (D8) | Toggle system standby on/off (camera UI keeps running unless your Linux app handles `EVENT:POWER_OFF`) |

### MCU serial protocol

| Direction | Message | Meaning |
| --- | --- | --- |
| MCU → Linux | `EVENT:KNOB_RIGHT` / `EVENT:KNOB_LEFT` | Modulino Knob rotation |
| MCU → Linux | `EVENT:CLICK` / `EVENT:LONG_PRESS_DEMO` | Knob press / long press |
| MCU → Linux | `EVENT:POWER_ON` / `EVENT:POWER_OFF` | Power-button toggle |
| MCU → Linux | `CLIMATE:<temp_c>,<rh_pct>` | Thermo reading every 2 s |
| Linux → MCU | `ZONE:<0-2>` | Highlight a zone on the LED matrix |
| Linux → MCU | `PROG:<0-13>` | Draw the scan progress bar |
| Linux → MCU | `ALERT:WATER` | Start the watering beep (every 3 s until cleared) |
| Linux → MCU | `ALERT:CLEAR` / `ALERT:OK` | Stop the watering beep |

The kiosk should send `ALERT:WATER` when a pot's `needs_water` flag turns true
and `ALERT:CLEAR` when it clears. Pressing the Modulino Knob also acknowledges
(stops) the beep locally.

The LED matrix mirrors the active choice: a highlighted 4-column zone (`ZONE:n`)
or a progress bar during scanning (`PROG:n`).

---

## 6. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: cv2` | Activate the venv, or run `./lighthouse_companion/setup_env.sh`. On macOS do **not** `pip3 install` into Homebrew Python. |
| `externally-managed-environment` from pip | Create and activate a venv first (see section 4). |
| No camera picture | Check the camera is index `0` and not in use by another app. The app falls back to a grey test frame. |
| MiDaS download fails | Fine — delete any partial `model-small.onnx` and rerun; the perspective-depth fallback is used. |
| Knob/button does nothing | Serial auto-detect currently scans `/dev/ttyACM*` and `/dev/ttyUSB*`. On macOS the board appears as `/dev/cu.usbmodem*`; run the MCU link on the UNO Q, or add that pattern in `main_kiosk.py::_init_serial`. |
| Distances look wrong | Reposition the camera, lock exposure, and confirm the printed ArUco square is exactly 4 cm. Tag #0 improves empty-balcony accuracy. |
| `WARN:KNOB_MISSING` / `WARN:THERMO_MISSING` / `WARN:BUZZER_MISSING` | A Modulino was not detected — check the Qwiic cable order and that it is fully seated. |
| Climate stuck at 22.5 °C / 55 % | Thermo not found — check its Qwiic connection; readings are replaced by fallback values. |
| Buzzer never sounds | The Linux app must send `ALERT:WATER`; confirm the serial link is open and the Buzzer module is detected. |
| Power button does nothing | Wire the button between **D8** and **GND**; it is read with `INPUT_PULLUP` and debounced for 60 ms. |

---

## Project layout

```text
lighthouse_companion/
├── mcu_firmware/
│   └── mcu_firmware.ino          # Modulino knob/thermo/buzzer, power button, LED matrix, serial protocol
├── linux_app/
│   ├── main_kiosk.py             # pygame kiosk state machine
│   ├── spatial_vision.py         # ArUco pinhole math + MiDaS depth + k-means zones
│   ├── plant_monitor.py          # canopy/height/yellowing/VPD watering advice
│   ├── generate_aruco_stakes.py  # printable 4 cm stake sheet generator
│   ├── guilds_db.json            # plant-guild compatibility database
│   └── requirements.txt
└── setup_env.sh                  # one-shot dependency + model + marker setup
```
