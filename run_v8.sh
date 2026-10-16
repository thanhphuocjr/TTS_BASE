#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Script khởi chạy container StreamingTTS-v8 trên server (Port 13128)
#
# Cách dùng:
#   ./run_v8.sh        # Chạy trên GPU 0 (mặc định)
#   ./run_v8.sh 0      # Chỉ định GPU 0
#   ./run_v8.sh 1      # Chỉ định GPU 1
# ══════════════════════════════════════════════════════════════════════════════

set -e

# GPU ID: Nhận tham số truyền vào hoặc biến môi trường GPU_ID, mặc định là 0
TARGET_GPU="${1:-${GPU_ID:-0}}"
DEVICE="cuda:${TARGET_GPU}"

echo "════════════════════════════════════════════════════════════════════"
echo "  Khởi động StreamingTTS-v8 (Port 13128 - Dual OmniVoice)"
echo "  Container: streamingtts-v8 | Image: streamingtts:v8"
echo "  Thiết bị: GPU ${TARGET_GPU} (${DEVICE})"
echo "  Port: 13128"
echo "════════════════════════════════════════════════════════════════════"

# 1. Tạo thư mục logs riêng cho v8
mkdir -p ~/Desktop/TTS_13128/logs

# 2. Build Docker Image streamingtts:v8
echo "[1/3] Đang build docker image streamingtts:v8..."
docker build -t streamingtts:v8 .

# 3. Dọn dẹp container streamingtts-v8 cũ nếu có
echo "[2/3] Dọn dẹp container streamingtts-v8 cũ nếu có..."
docker rm -f streamingtts-v8 2>/dev/null || true

# 4. Khởi chạy container streamingtts-v8 ở cổng 13128
echo "[3/3] Khởi chạy container streamingtts-v8 trên cổng 13128 (GPU ${TARGET_GPU})..."
docker run -d \
  --name streamingtts-v8 \
  --restart unless-stopped \
  --gpus all \
  -e TTS_DEVICE="${DEVICE}" \
  -e TTS_VIETTTS_DEVICE="${DEVICE}" \
  -e TTS_ENGTTS_DEVICE="${DEVICE}" \
  -e PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
  -p 13128:13128 \
  -v ~/Desktop/TTS_13128/logs:/app/logs \
  -v ~/Desktop/streamingtts-v8/voices:/app/voices \
  -v ~/Desktop/streamingtts-v8/models/engtts:/app/models/engtts \
  streamingtts:v8

echo ""
echo "✅ Container streamingtts-v8 đã khởi động thành công trên cổng 13128 (GPU ${TARGET_GPU})!"
echo "Server URL: http://0.0.0.0:13128"
echo "Theo dõi log thời gian thực:"
echo "------------------------------------------------------------------"
docker logs -f streamingtts-v8
