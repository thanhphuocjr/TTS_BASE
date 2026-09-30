#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Script đồng bộ code StreamingTTS từ Mac lên GPU Server
# Server: ai@192.168.91.176 (Port 2225)
# Thư mục đích: ~/Desktop/streamingtts-v7
# ══════════════════════════════════════════════════════════════════════════════

set -e

SERVER_USER="ai"
SERVER_IP="192.168.91.176"
SERVER_PORT="2225"
REMOTE_DIR="~/Desktop/streamingtts-v7"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "════════════════════════════════════════════════════════════════════"
echo "  Đồng bộ StreamingTTS lên Server: ${SERVER_USER}@${SERVER_IP}:${SERVER_PORT}"
echo "  Thư mục đích: ${REMOTE_DIR}"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Đồng bộ code và voices lên server (loại trừ model nặng, log, git để sync siêu nhanh)
rsync -avz --progress \
    -e "ssh -p ${SERVER_PORT}" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".DS_Store" \
    --exclude ".git" \
    --exclude "logs" \
    --exclude "server_logs" \
    --exclude "models" \
    --exclude "*.wav" \
    "${LOCAL_DIR}/app" \
    "${LOCAL_DIR}/config" \
    "${LOCAL_DIR}/engines" \
    "${LOCAL_DIR}/text_normalizer" \
    "${LOCAL_DIR}/presets" \
    "${LOCAL_DIR}/requirements.txt" \
    "${LOCAL_DIR}/Dockerfile" \
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"

# Đồng bộ riêng thư mục voices (bao gồm cả các file wav mẫu mới như north1.wav, south2.wav...)
rsync -avz --progress \
    -e "ssh -p ${SERVER_PORT}" \
    --exclude "__pycache__" \
    --exclude ".DS_Store" \
    "${LOCAL_DIR}/voices/" \
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/voices/"

echo ""
echo "✅ Đồng bộ hoàn tất lên server!"
echo ""
echo "Bước tiếp theo: Trên terminal server (ai@AI-Server-FSP), chạy các lệnh sau:"
echo "------------------------------------------------------------------"
echo "cd ~/Desktop/streamingtts-v7"
echo "docker tag streamingtts:v7 streamingtts:v5 2>/dev/null || true"
echo "docker build -t streamingtts:v7 ."
echo "docker rm -f streamingtts-v7"
echo "docker run -d \\"
echo "  --name streamingtts-v7 \\"
echo "  --restart unless-stopped \\"
echo "  --gpus all \\"
echo "  -p 13127:13127 \\"
echo "  -v ~/Desktop/TTS_13127/logs:/app/logs \\"
echo "  -v ~/Desktop/streamingtts-v7/voices:/app/voices \\"
echo "  streamingtts:v7"
echo "docker logs -f streamingtts-v7"
echo "════════════════════════════════════════════════════════════════════"
