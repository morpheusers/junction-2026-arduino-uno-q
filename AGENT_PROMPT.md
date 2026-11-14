# OPENCODE AGENT INSTRUCTIONS: THE LIGHTHOUSE COMPANION (ARDUINO UNO Q)

You are an autonomous coding agent. Set up and write the complete codebase for our hackathon project **"The Lighthouse Companion"** targeting the **Arduino UNO Q** (STM32U585 MCU + Qualcomm QRB2210 Linux MPU) and **TPX00246 USB Camera**.

Execute the following tasks step-by-step using your file-creation and shell-execution tools. Do not use placeholders or truncate any code.

---

## STEP 1: CREATE DIRECTORY STRUCTURE

Create the following project directory tree in the current workspace:

~~~text
lighthouse_companion/
├── mcu_firmware/
│   └── mcu_firmware.ino
├── linux_app/
│   ├── guilds_db.json
│   ├── spatial_vision.py
│   ├── plant_monitor.py
│   ├── main_kiosk.py
│   ├── generate_aruco_stakes.py
│   └── requirements.txt
└── setup_env.sh
~~~

---

## STEP 2: WRITE THE FILES EXACTLY AS SPECIFIED

### File 1: `lighthouse_companion/linux_app/requirements.txt`

~~~text
opencv-contrib-python>=4.8.0
numpy>=1.24.0
pygame>=2.5.0
pyserial>=3.5
~~~

### File 2: `lighthouse_companion/setup_env.sh`
Write this shell script and make it executable (`chmod +x lighthouse_companion/setup_env.sh`):

~~~bash
#!/usr/bin/env bash
set -e

echo "[1/3] Installing Python dependencies..."
pip3 install -r "\$(dirname "\$0")/linux_app/requirements.txt"

echo "[2/3] Downloading MiDaS v2.1 Small ONNX model for Monocular 3D Depth..."
MODEL_PATH="\$(dirname "\$0")/linux_app/model-small.onnx"
if [ ! -f "\$MODEL_PATH" ]; then
    wget -q --show-progress -O "\$MODEL_PATH" "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx" || echo "Warning: Could not download MiDaS ONNX. Fallback perspective depth will be used."
fi

echo "[3/3] Generating printable 4cm ArUco wooden stake markers..."
python3 "\$(dirname "\$0")/linux_app/generate_aruco_stakes.py"
echo "Setup complete! Run: cd lighthouse_companion/linux_app && python3 main_kiosk.py"
~~~

### File 3: `lighthouse_companion/mcu_firmware/mcu_firmware.ino`

~~~cpp
#include <Wire.h>
#include <Arduino_LED_Matrix.h>
#include <Adafruit_BME280.h>

ArduinoLEDMatrix matrix;
Adafruit_BME280 bme;

const int PIN_CLK = 2;
const int PIN_DT  = 3;
const int PIN_SW  = 4;

int lastClkState;
unsigned long btnPressTime = 0;
bool btnHeld = false;
unsigned long lastSensorPush = 0;

uint8_t frame[8][13] = {0};

void highlightZoneOnMatrix(int zoneIdx) {
  memset(frame, 0, sizeof(frame));
  int startCol = (zoneIdx % 3) * 4;
  for (int r = 1; r < 7; r++) {
    for (int c = startCol; c < startCol + 4 && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  matrix.renderBitmap(frame, 8, 13);
}

void drawProgress(int cols) {
  memset(frame, 0, sizeof(frame));
  for (int r = 2; r < 6; r++) {
    for (int c = 0; c < cols && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  matrix.renderBitmap(frame, 8, 13);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  matrix.begin();

  pinMode(PIN_CLK, INPUT_PULLUP);
  pinMode(PIN_DT, INPUT_PULLUP);
  pinMode(PIN_SW, INPUT_PULLUP);
  lastClkState = digitalRead(PIN_CLK);

  bme.begin(0x76);
  drawProgress(1);
}

void loop() {
  int currentClk = digitalRead(PIN_CLK);
  if (currentClk != lastClkState && currentClk == LOW) {
    if (digitalRead(PIN_DT) != currentClk) {
      Serial.println("EVENT:KNOB_RIGHT");
    } else {
      Serial.println("EVENT:KNOB_LEFT");
    }
  }
  lastClkState = currentClk;

  if (digitalRead(PIN_SW) == LOW) {
    if (btnPressTime == 0) btnPressTime = millis();
    if (!btnHeld && (millis() - btnPressTime > 1500)) {
      Serial.println("EVENT:LONG_PRESS_DEMO");
      btnHeld = true;
    }
  } else {
    if (btnPressTime > 0 && !btnHeld && (millis() - btnPressTime > 50)) {
      Serial.println("EVENT:CLICK");
    }
    btnPressTime = 0;
    btnHeld = false;
  }

  if (millis() - lastSensorPush > 2000) {
    float temp = bme.readTemperature();
    float hum  = bme.readHumidity();
    if (isnan(temp)) { temp = 22.5; hum = 55.0; }
    Serial.print("CLIMATE:");
    Serial.print(temp, 1);
    Serial.print(",");
    Serial.println(hum, 1);
    lastSensorPush = millis();
  }

  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("ZONE:")) {
      int z = cmd.substring(5).toInt();
      highlightZoneOnMatrix(z);
    } else if (cmd.startsWith("PROG:")) {
      int p = cmd.substring(5).toInt();
      drawProgress(p);
    }
  }
}
~~~

### File 4: `lighthouse_companion/linux_app/guilds_db.json`

~~~json
{
  "guilds": [
    {
      "id": "mediterranean_sun",
      "name": "Sunny Mediterranean Trio",
      "min_sun_hours": 5.5,
      "min_temp_c": 16.0,
      "plants": ["Dwarf Tomato (A)", "Genovese Basil (B)", "French Marigold (C)"],
      "why_it_works": "Basil repels flies, Marigold stops root pests, Tomato shades the soil.",
      "stencil_guide": "Hole A: 1 Tomato | Hole B: 2 Basil | Hole C: 2 Marigold"
    },
    {
      "id": "continental_half_shade",
      "name": "Half-Shade Balcony Guild",
      "min_sun_hours": 2.5,
      "min_temp_c": 10.0,
      "plants": ["Oakleaf Lettuce (A)", "Chives (B)", "Wild Strawberry (C)"],
      "why_it_works": "Strawberries act as living mulch to lock in moisture; Chives deter aphids.",
      "stencil_guide": "Hole A: 2 Lettuce | Hole B: Clump Chives | Hole C: 1 Strawberry"
    },
    {
      "id": "cool_nordic_shade",
      "name": "Cool Shade Forest Trio",
      "min_sun_hours": 0.0,
      "min_temp_c": 5.0,
      "plants": ["Woodruff / Mint (A)", "Curly Parsley (B)", "Pansy (C)"],
      "why_it_works": "Thrives in indirect light and cool drafts with almost zero watering.",
      "stencil_guide": "Hole A: 1 Mint | Hole B: 3 Parsley | Hole C: 2 Pansies"
    }
  ]
}
~~~

### File 5: `lighthouse_companion/linux_app/spatial_vision.py`

~~~python
import os
import json
import subprocess
import cv2
import numpy as np

FOCAL_LENGTH_PX = 880.0   # Calibrated for TPX00246 (80-deg FOV at 1280x720)
TAG_REAL_WIDTH_CM = 4.0   # 4cm x 4cm ArUco wooden stake
ANCHOR_TAG_ID = 0         # Optional Tag #0 used to anchor real cm on an empty balcony

class BalconySpatialEngine:
    def __init__(self, midas_onnx_path="model-small.onnx", db_path="guilds_db.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        midas_full = os.path.join(base_dir, midas_onnx_path)
        db_full = os.path.join(base_dir, db_path)

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, cv2.aruco.DetectorParameters())

        self.has_midas = os.path.exists(midas_full)
        if self.has_midas:
            self.midas_net = cv2.dnn.readNet(midas_full)

        with open(db_full, "r") as f:
            self.guilds_db = json.load(f)["guilds"]

        self.sun_accumulator = None
        self.sample_count = 0

    @staticmethod
    def lock_camera_exposure(device="/dev/video0"):
        try:
            subprocess.run(
                ["v4l2-ctl", "-d", device, "-c", "auto_exposure=1", "-c", "exposure_time_absolute=150"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    def _measure_tag(self, pts):
        tag_px_w = float(np.linalg.norm(pts[0] - pts[1]))
        tag_px_h = float(np.linalg.norm(pts[1] - pts[2]))
        cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
        dist_cm = (TAG_REAL_WIDTH_CM * FOCAL_LENGTH_PX) / max(tag_px_w, 1.0)
        return cx, cy, tag_px_w, tag_px_h, dist_cm

    def detect_initial_layout(self, frame, yolo_pot_boxes=None):
        h, w, _ = frame.shape
        self.sun_accumulator = np.zeros((h, w), dtype=np.float32)
        self.sample_count = 0

        corners, ids, _ = self.detector.detectMarkers(frame)
        tag_list = ids.flatten().tolist() if ids is not None else []
        pot_indices = [i for i, tid in enumerate(tag_list) if tid != ANCHOR_TAG_ID]

        # BRANCH A: EXISTING POTS DETECTED VIA WOODEN STAKES (Method 2: Pinhole Math)
        if len(pot_indices) > 0:
            spots = []
            for i in pot_indices:
                tid = int(tag_list[i])
                cx, cy, tag_w, tag_h, dist_cm = self._measure_tag(corners[i][0])
                half_b = int(tag_w * 2.5)
                bbox = [max(0, cx - half_b), max(0, cy - half_b), min(w, cx + half_b), min(h, cy + half_b)]
                pot_diam_cm = round(((bbox[2] - bbox[0]) / tag_w) * TAG_REAL_WIDTH_CM, 1)

                if yolo_pot_boxes:
                    for (x1, y1, x2, y2) in yolo_pot_boxes:
                        if x1 <= cx <= x2 and y1 <= cy <= y2:
                            pot_diam_cm = round(((x2 - x1) / tag_w) * TAG_REAL_WIDTH_CM, 1)
                            bbox = [int(x1), int(y1), int(x2), int(y2)]
                            break

                spots.append({
                    "id": f"Pot #{tid}",
                    "tag_id": tid,
                    "tag_px_h": tag_h,
                    "distance_cm": round(dist_cm, 1),
                    "diameter_cm": pot_diam_cm,
                    "bbox": bbox,
                    "mask": None
                })
            return "EXISTING_POTS", spots

        # BRANCH B: EMPTY BALCONY (Method 1: MiDaS Depth + Adaptive 1D K-Means)
        if self.has_midas:
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (256, 256), (0.485, 0.456, 0.406), swapRB=True)
            self.midas_net.setInput(blob)
            depth_raw = cv2.resize(self.midas_net.forward()[0, :, :], (w, h))
        else:
            depth_raw = np.tile(np.linspace(0.1, 1.0, h, dtype=np.float32).reshape(h, 1), (1, w))

        cutoff = np.percentile(depth_raw, 15)
        valid_mask = depth_raw > cutoff
        valid_depths = depth_raw[valid_mask].reshape(-1, 1).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(valid_depths, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        sorted_ids = np.argsort(centers.flatten())[::-1]

        full_labels = np.full((h, w), -1, dtype=int)
        full_labels[valid_mask] = labels.flatten()

        scale_k = None
        if ANCHOR_TAG_ID in tag_list:
            idx = tag_list.index(ANCHOR_TAG_ID)
            ax, ay, _, _, anchor_dist_cm = self._measure_tag(corners[idx][0])
            inv_d = float(depth_raw[ay, ax])
            if inv_d > 1e-3:
                scale_k = anchor_dist_cm * inv_d

        zone_titles = ["Zone A (Near Foreground)", "Zone B (Mid Balcony)", "Zone C (Far Railing)"]
        spots = []
        for rank, cid in enumerate(sorted_ids):
            mask = (full_labels == cid)
            center_inv_d = float(centers[cid][0])
            est_dist = round(scale_k / center_inv_d, 1) if scale_k else round((rank + 1) * 90.0, 1)

            contours, _ = cv2.findContours((mask.astype(np.uint8)) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                x, y, bw, bh = cv2.boundingRect(max(contours, key=cv2.contourArea))
                bbox = [x, y, x + bw, y + bh]
            else:
                bbox = [int(rank * w / 3), int(h * 0.3), int((rank + 1) * w / 3), h - 10]

            spots.append({
                "id": zone_titles[rank],
                "tag_id": rank + 1,
                "tag_px_h": 50.0,
                "distance_cm": est_dist,
                "diameter_cm": 24.0,
                "bbox": bbox,
                "mask": mask
            })
        return "EMPTY_BALCONY", spots

    def accumulate_sunlight_step(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sunlit = (gray > 175).astype(np.float32)
        self.sun_accumulator += sunlit
        self.sample_count += 1

    def finalize_phase1_recommendations(self, spots, avg_temp_c):
        sun_hours_map = (self.sun_accumulator / max(self.sample_count, 1)) * 10.0

        for spot in spots:
            if spot["mask"] is not None:
                sun_h = float(np.mean(sun_hours_map[spot["mask"]]))
            else:
                x1, y1, x2, y2 = spot["bbox"]
                sun_h = float(np.mean(sun_hours_map[y1:y2, x1:x2]))

            spot["sun_hours"] = round(sun_h, 1)

            chosen_guild = self.guilds_db[-1]
            for g in self.guilds_db:
                if sun_h >= g["min_sun_hours"] and avg_temp_c >= g["min_temp_c"]:
                    chosen_guild = g
                    break
            spot["guild"] = chosen_guild
        return spots
~~~

### File 6: `lighthouse_companion/linux_app/plant_monitor.py`

~~~python
import cv2
import numpy as np

class OpticalPlantMonitor:
    def evaluate_pot(self, frame_bgr, spot, temp_c, rh_pct):
        x1, y1, x2, y2 = spot["bbox"]
        crop = frame_bgr[max(0, y1):max(1, y2), max(0, x1):max(1, x2)]
        if crop.size == 0:
            return {"action_msg": "NO VIEW", "needs_water": False, "height_cm": 0.0, "canopy_pct": 0.0, "vpd_kpa": 1.0}

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # 1. Green Biomass & Real Height in cm (calibrated against 4cm ArUco stake)
        green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
        canopy_pct = (np.sum(green_mask > 0) / float(green_mask.size)) * 100.0

        coords = np.column_stack(np.where(green_mask > 0))
        if len(coords) > 10:
            px_height = float(coords[:, 0].max() - coords[:, 0].min())
            height_cm = (px_height / max(spot.get("tag_px_h", 50.0), 1.0)) * 4.0
        else:
            height_cm = 0.5

        # 2. Leaf Yellowing / Stress Check
        yellow_mask = cv2.inRange(hsv, np.array([15, 50, 50]), np.array([34, 255, 255]))
        yellow_ratio = np.sum(yellow_mask > 0) / float(np.sum(green_mask > 0) + 1.0)

        # 3. VPD (kPa) + Soil Luminance -> Thirst Score
        svp = 0.61078 * np.exp((17.27 * temp_c) / (temp_c + 237.3))
        vpd_kpa = svp * (1.0 - (rh_pct / 100.0))

        soil_pixels = hsv[:, :, 2][green_mask == 0]
        soil_luminance = float(np.mean(soil_pixels)) if len(soil_pixels) > 0 else 110.0

        sun_h = spot.get("sun_hours", 5.0)
        thirst_index = (soil_luminance / 255.0) * 0.5 + (min(vpd_kpa, 2.5) / 2.5) * 0.3 + (sun_h / 10.0) * 0.2
        needs_water = thirst_index > 0.58

        if needs_water:
            action_msg = "THIRSTY: Give 2 cups of water today!"
        elif yellow_ratio > 0.25:
            action_msg = "STRESS: Leaves yellowing (Check shade)"
        else:
            action_msg = "THRIVING: Soil moist & growing well!"

        return {
            "canopy_pct": round(canopy_pct, 1),
            "height_cm": round(height_cm, 1),
            "vpd_kpa": round(vpd_kpa, 2),
            "needs_water": needs_water,
            "action_msg": action_msg
        }
~~~

### File 7: `lighthouse_companion/linux_app/main_kiosk.py`

~~~python
import pygame
import cv2
import numpy as np
import serial
import glob
from spatial_vision import BalconySpatialEngine
from plant_monitor import OpticalPlantMonitor

BG_CREAM    = (248, 244, 232)
TEXT_BLACK  = (20, 20, 20)
ACCENT_GOLD = (230, 140, 0)
ALERT_RED   = (200, 40, 40)
OK_GREEN    = (30, 130, 50)

class LighthouseKioskApp:
    def __init__(self, camera_idx=0):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 480))
        pygame.display.set_caption("The Lighthouse Companion - UNO Q")
        self.font_lg = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_md = pygame.font.SysFont("Arial", 21, bold=True)

        self.ser = self._init_serial()
        self.cap = cv2.VideoCapture(camera_idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        BalconySpatialEngine.lock_camera_exposure()

        self.spatial = BalconySpatialEngine()
        self.monitor = OpticalPlantMonitor()

        self.state = "BOOT_CONFIRM"
        self.mode = "EMPTY_BALCONY"
        self.spots = []
        self.selected_idx = 0
        self.scan_ticks = 0
        self.temp_c = 23.0
        self.hum_pct = 52.0
        self.snapshot = None
        self.run_initial_detection()

    def _init_serial(self):
        ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
        for p in ports:
            try:
                return serial.Serial(p, 115200, timeout=0.01)
            except Exception:
                pass
        return None

    def _send_mcu(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd + "\n").encode("utf-8"))
            except Exception:
                pass

    def _poll_mcu_events(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "EVENT:KNOB_RIGHT" and len(self.spots) > 0:
                    self.selected_idx = (self.selected_idx + 1) % len(self.spots)
                    self._send_mcu(f"ZONE:{self.selected_idx}")
                elif line == "EVENT:KNOB_LEFT" and len(self.spots) > 0:
                    self.selected_idx = (self.selected_idx - 1) % len(self.spots)
                    self._send_mcu(f"ZONE:{self.selected_idx}")
                elif line in ("EVENT:CLICK", "EVENT:LONG_PRESS_DEMO"):
                    self.advance_state()
                elif line.startswith("CLIMATE:"):
                    parts = line.split(":")[1].split(",")
                    self.temp_c = float(parts[0])
                    self.hum_pct = float(parts[1])
        except Exception:
            pass

    def run_initial_detection(self):
        ret, frame = self.cap.read()
        if not ret or frame is None:
            frame = np.full((720, 1280, 3), 120, dtype=np.uint8)
        self.snapshot = frame.copy()
        self.mode, self.spots = self.spatial.detect_initial_layout(frame)
        self.selected_idx = 0

    def draw_camera_with_boxes(self, frame):
        disp = frame.copy()
        for i, s in enumerate(self.spots):
            x1, y1, x2, y2 = s["bbox"]
            color = (0, 200, 255) if i == self.selected_idx else (180, 180, 180)
            thickness = 6 if i == self.selected_idx else 2
            cv2.rectangle(disp, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(disp, s["id"], (x1 + 8, max(35, y1 + 35)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

        disp_rgb = cv2.cvtColor(cv2.resize(disp, (760, 250)), cv2.COLOR_BGR2RGB)
        surf = pygame.surfarray.make_surface(np.rot90(np.fliplr(disp_rgb)))
        self.screen.blit(surf, (20, 15))

    def render_text_line(self, text, y, color=TEXT_BLACK, large=False):
        font = self.font_lg if large else self.font_md
        surf = font.render(text, True, color)
        self.screen.blit(surf, (25, y))

    def step_loop(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            self.screen.fill(BG_CREAM)
            self._poll_mcu_events()

            ret, live_frame = self.cap.read()
            if not ret or live_frame is None:
                live_frame = self.snapshot

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RIGHT and len(self.spots) > 0:
                        self.selected_idx = (self.selected_idx + 1) % len(self.spots)
                        self._send_mcu(f"ZONE:{self.selected_idx}")
                    elif event.key == pygame.K_LEFT and len(self.spots) > 0:
                        self.selected_idx = (self.selected_idx - 1) % len(self.spots)
                        self._send_mcu(f"ZONE:{self.selected_idx}")
                    elif event.key == pygame.K_RETURN:
                        self.advance_state()

            if self.state == "BOOT_CONFIRM":
                self.draw_camera_with_boxes(self.snapshot)
                if self.mode == "EXISTING_POTS":
                    msg = f"FOUND {len(self.spots)} EMPTY POTS ON YOUR BALCONY!"
                else:
                    msg = "EMPTY BALCONY DETECTED (3 3D Depth Zones Mapped)"
                self.render_text_line(msg, 280, ACCENT_GOLD, large=True)
                self.render_text_line("Press KNOB (or Enter) to start 24h Sunlight Scan", 335)
                self.render_text_line(f"Current Climate: {self.temp_c}C | Humidity: {self.hum_pct}%", 385)

            elif self.state == "SCANNING":
                self.spatial.accumulate_sunlight_step(live_frame)
                self.scan_ticks += 1
                self._send_mcu(f"PROG:{int(self.scan_ticks * 1.3)}")
                self.draw_camera_with_boxes(live_frame)
                pct = int((self.scan_ticks / 10.0) * 100)
                self.render_text_line(f"SCANNING BALCONY MICRO-CLIMATE... {pct}%", 290, ACCENT_GOLD, large=True)
                self.render_text_line("Shine flashlight on a pot/zone to simulate sunny hours!", 350)
                pygame.time.wait(400)
                if self.scan_ticks >= 10:
                    self.spots = self.spatial.finalize_phase1_recommendations(self.spots, self.temp_c)
                    self.state = "PHASE1_PLAN"
                    self._send_mcu(f"ZONE:{self.selected_idx}")

            elif self.state == "PHASE1_PLAN":
                self.draw_camera_with_boxes(self.snapshot)
                spot = self.spots[self.selected_idx]
                g = spot["guild"]
                self.render_text_line(
                    f"{spot['id']} ({spot['sun_hours']}h Sun | Dist: {spot['distance_cm']}cm)",
                    275, ACCENT_GOLD, large=True
                )
                self.render_text_line(f"PLANT: {', '.join(g['plants'])}", 320, OK_GREEN, large=True)
                self.render_text_line(f"STENCIL: {g['stencil_guide']}", 365)
                self.render_text_line("[Turn Knob: Switch Spot]  [Click Knob: Start Phase 2 Care]", 420)

            elif self.state == "PHASE2_CARE":
                self.draw_camera_with_boxes(live_frame)
                spot = self.spots[self.selected_idx]
                status = self.monitor.evaluate_pot(live_frame, spot, self.temp_c, self.hum_pct)
                color = ALERT_RED if status["needs_water"] else OK_GREEN

                self.render_text_line(f"PHASE 2 MONITOR: {spot['id']}", 275, TEXT_BLACK, large=True)
                self.render_text_line(status["action_msg"], 320, color, large=True)
                self.render_text_line(
                    f"Height: {status['height_cm']} cm | Canopy: {status['canopy_pct']}% | VPD: {status['vpd_kpa']} kPa",
                    370
                )
                self.render_text_line("[Turn Knob: Check Next Pot]  [Click Knob: Re-Scan Space]", 420)

            pygame.display.flip()
            clock.tick(15)

        self.cap.release()
        pygame.quit()

    def advance_state(self):
        if self.state == "BOOT_CONFIRM":
            self.scan_ticks = 0
            self.state = "SCANNING"
        elif self.state == "PHASE1_PLAN":
            self.state = "PHASE2_CARE"
        elif self.state == "PHASE2_CARE":
            self.run_initial_detection()
            self.state = "BOOT_CONFIRM"

if __name__ == "__main__":
    app = LighthouseKioskApp(camera_idx=0)
    app.step_loop()
~~~

### File 8: `lighthouse_companion/linux_app/generate_aruco_stakes.py`

~~~python
import os
import cv2
import numpy as np

def generate_stakes_sheet():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    sheet = np.full((1400, 2200), 255, dtype=np.uint8)
    tag_size_px = 472

    for tag_id in range(4):
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, tag_id, tag_size_px)
        x_offset = 80 + tag_id * 520
        y_offset = 200
        sheet[y_offset:y_offset + tag_size_px, x_offset:x_offset + tag_size_px] = marker_img
        label = "Anchor #0 (Empty)" if tag_id == 0 else f"Pot Stake #{tag_id}"
        cv2.putText(sheet, label, (x_offset, y_offset - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 3)

    out_path = os.path.join(out_dir, "printable_4cm_aruco_stakes.png")
    cv2.imwrite(out_path, sheet)
    print(f"Saved printable 4cm ArUco stakes sheet to: {out_path}")

if __name__ == "__main__":
    generate_stakes_sheet()
~~~

---

## STEP 3: VERIFY & TEST
After creating all files:
1. Run `python3 -m py_compile lighthouse_companion/linux_app/*.py` to verify there are zero syntax errors.
2. Run `python3 lighthouse_companion/linux_app/generate_aruco_stakes.py` to generate the printable ArUco tags image (`printable_4cm_aruco_stakes.png`).
3. Report back with a summary of the created files and confirmation that all checks passed.
