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
