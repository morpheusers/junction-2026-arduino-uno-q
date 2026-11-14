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
