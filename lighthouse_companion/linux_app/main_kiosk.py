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
