#!/usr/bin/env bash
set -e

echo "[1/3] Installing Python dependencies..."
pip3 install -r "$(dirname "$0")/linux_app/requirements.txt"

echo "[2/3] Downloading MiDaS v2.1 Small ONNX model for Monocular 3D Depth..."
MODEL_PATH="$(dirname "$0")/linux_app/model-small.onnx"
MODEL_URL="https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx"
if [ ! -f "$MODEL_PATH" ]; then
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress -O "$MODEL_PATH" "$MODEL_URL"
    elif command -v curl >/dev/null 2>&1; then
        curl -L --fail --progress-bar -o "$MODEL_PATH" "$MODEL_URL"
    else
        echo "Warning: Neither wget nor curl found. Falling back to perspective depth."
    fi || echo "Warning: Could not download MiDaS ONNX. Fallback perspective depth will be used."
fi

echo "[3/3] Generating printable 4cm ArUco wooden stake markers..."
python3 "$(dirname "$0")/linux_app/generate_aruco_stakes.py"
echo "Setup complete! Run: cd lighthouse_companion/linux_app && python3 main_kiosk.py"
