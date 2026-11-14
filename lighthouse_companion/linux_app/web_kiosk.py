"""Tiny local web mirror of the Lighthouse Companion PyGame kiosk.

Mirrors the exact layout/colors/text of main_kiosk.py but served over HTTP so
the demo works without the UNO Q's physical 4.3" screen. State machine, vision
pipeline and keyboard controls are reused verbatim from LighthouseKioskApp.

Run:  python3 web_kiosk.py   (then open http://127.0.0.1:8080)
"""
import base64
import io
import json
import threading
import time

import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from main_kiosk import LighthouseKioskApp

HOST = "127.0.0.1"
PORT = 8080
WIDTH, HEIGHT = 800, 480

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Lighthouse Companion</title>
<style>
  body { margin:0; background:#F8F4E8; color:#141414; font-family:Arial,sans-serif; }
  #stage { width:800px; height:480px; margin:20px auto; position:relative;
           background:#F8F4E8; border:1px solid #141414; }
  #cam { position:absolute; left:20px; top:15px; width:760px; height:250px; }
  .line { position:absolute; left:25px; font-weight:bold; }
  .lg { font-size:28px; } .md { font-size:21px; }
  .gold { color:#E68C00; } .red { color:#C82828; } .green { color:#1E8232; }
  #help { text-align:center; margin-top:8px; font-size:14px; }
</style></head><body>
<div id="stage">
  <img id="cam" alt="camera"/>
  <div id="l0" class="line lg gold" style="top:280px"></div>
  <div id="l1" class="line md" style="top:335px"></div>
  <div id="l2" class="line md" style="top:385px"></div>
</div>
<div id="help">Keys: Left/Right arrows switch spot, Enter advances state. (mirrors rotary knob)</div>
<script>
let state = null;
async function poll(){
  const r = await fetch('/state'); state = await r.json();
  document.getElementById('cam').src = 'data:image/jpeg;base64,' + state.frame;
  const lines = state.lines;
  for (let i=0;i<3;i++){
    const el = document.getElementById('l'+i);
    el.textContent = lines[i]||'';
    el.className = 'line ' + (lines[i]&&lines[i].large?'lg ':'md ') + (lines[i]?lines[i].color:'');
  }
  setTimeout(poll, 200);
}
document.addEventListener('keydown', e=>{
  let key=null;
  if(e.key==='ArrowRight') key='right';
  if(e.key==='ArrowLeft') key='left';
  if(e.key==='Enter') key='enter';
  if(key){ fetch('/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})}); }
});
poll();
</script></body></html>"""


class WebKiosk(LighthouseKioskApp):
    def __init__(self, camera_idx=0):
        # Avoid pygame display; init only what we need by calling parent but
        # overriding screen usage is not needed because we never call step_loop.
        super().__init__(camera_idx)
        self._lock = threading.Lock()
        self._lines = []
        self._frame_b64 = ""
        self._running = True

    def _render_frame_to_b64(self, frame):
        ok, buf = cv2.imencode(".jpg", frame)
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    def _compose(self, state_name, snapshot_or_live):
        # Reproduce draw_camera_with_boxes into an image for the web.
        disp = snapshot_or_live.copy() if snapshot_or_live is not None else np.full((720, 1280, 3), 120, dtype=np.uint8)
        for i, s in enumerate(self.spots):
            x1, y1, x2, y2 = s["bbox"]
            color = (0, 200, 255) if i == self.selected_idx else (180, 180, 180)
            thickness = 6 if i == self.selected_idx else 2
            cv2.rectangle(disp, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(disp, s["id"], (x1 + 8, max(35, y1 + 35)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
        disp = cv2.resize(disp, (760, 250))
        return self._render_frame_to_b64(disp)

    def run_web_loop(self):
        while self._running:
            self._poll_mcu_events()
            ret, live_frame = self.cap.read()
            if not ret or live_frame is None:
                live_frame = self.snapshot

            with self._lock:
                if self.state == "BOOT_CONFIRM":
                    self._frame_b64 = self._compose(self.state, self.snapshot)
                    msg = f"FOUND {len(self.spots)} EMPTY POTS ON YOUR BALCONY!" if self.mode == "EXISTING_POTS" else "EMPTY BALCONY DETECTED (3 3D Depth Zones Mapped)"
                    self._lines = [
                        {"text": msg, "large": True, "color": "gold"},
                        {"text": "Press KNOB (or Enter) to start 24h Sunlight Scan", "large": False, "color": ""},
                        {"text": f"Current Climate: {self.temp_c}C | Humidity: {self.hum_pct}%", "large": False, "color": ""},
                    ]
                elif self.state == "SCANNING":
                    self.spatial.accumulate_sunlight_step(live_frame)
                    self.scan_ticks += 1
                    self._send_mcu(f"PROG:{int(self.scan_ticks * 1.3)}")
                    self._frame_b64 = self._compose(self.state, live_frame)
                    pct = int((self.scan_ticks / 10.0) * 100)
                    self._lines = [
                        {"text": f"SCANNING BALCONY MICRO-CLIMATE... {pct}%", "large": True, "color": "gold"},
                        {"text": "Shine flashlight on a pot/zone to simulate sunny hours!", "large": False, "color": ""},
                        {"text": "", "large": False, "color": ""},
                    ]
                    time.sleep(0.4)
                    if self.scan_ticks >= 10:
                        self.spots = self.spatial.finalize_phase1_recommendations(self.spots, self.temp_c)
                        self.state = "PHASE1_PLAN"
                        self._send_mcu(f"ZONE:{self.selected_idx}")
                elif self.state == "PHASE1_PLAN":
                    self._frame_b64 = self._compose(self.state, self.snapshot)
                    spot = self.spots[self.selected_idx]
                    g = spot["guild"]
                    self._lines = [
                        {"text": f"{spot['id']} ({spot['sun_hours']}h Sun | Dist: {spot['distance_cm']}cm)", "large": True, "color": "gold"},
                        {"text": f"PLANT: {', '.join(g['plants'])}", "large": True, "color": "green"},
                        {"text": f"STENCIL: {g['stencil_guide']}", "large": False, "color": ""},
                    ]
                elif self.state == "PHASE2_CARE":
                    self._frame_b64 = self._compose(self.state, live_frame)
                    spot = self.spots[self.selected_idx]
                    status = self.monitor.evaluate_pot(live_frame, spot, self.temp_c, self.hum_pct)
                    color = "red" if status["needs_water"] else "green"
                    self._lines = [
                        {"text": f"PHASE 2 MONITOR: {spot['id']}", "large": True, "color": ""},
                        {"text": status["action_msg"], "large": True, "color": color},
                        {"text": f"Height: {status['height_cm']} cm | Canopy: {status['canopy_pct']}% | VPD: {status['vpd_kpa']} kPa", "large": False, "color": ""},
                    ]
            time.sleep(1 / 15)

    def handle_input(self, key):
        with self._lock:
            if key == "right" and self.spots:
                self.selected_idx = (self.selected_idx + 1) % len(self.spots)
                self._send_mcu(f"ZONE:{self.selected_idx}")
            elif key == "left" and self.spots:
                self.selected_idx = (self.selected_idx - 1) % len(self.spots)
                self._send_mcu(f"ZONE:{self.selected_idx}")
            elif key == "enter":
                self.advance_state()

    def get_state(self):
        with self._lock:
            return {"frame": self._frame_b64, "lines": self._lines, "state": self.state}

    def stop(self):
        self._running = False
        self.cap.release()


app = WebKiosk(camera_idx=0)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            data = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/state":
            data = json.dumps(app.get_state()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/input":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n))
            app.handle_input(body.get("key"))
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    t = threading.Thread(target=app.run_web_loop, daemon=True)
    t.start()
    print(f"Lighthouse Companion web mirror running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
