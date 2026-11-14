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
