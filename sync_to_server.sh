#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Script đồng bộ StreamingTTS từ Mac lên GPU Server
# Server: ai@192.168.91.176 (Port 2225)
# Thư mục đích: ~/Desktop/Ominivoice-TTS
#
# Chỉ gửi những gì cần để build + chạy: code, Dockerfile, requirements,
# run.sh, voices/, models/ (viettts, engtts, normalizer) và README.md.
# ══════════════════════════════════════════════════════════════════════════════

set -e

SERVER_USER="ai"
SERVER_IP="192.168.91.176"
SERVER_PORT="2225"
REMOTE_DIR="~/Desktop/Ominivoice-TTS"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH="ssh -p ${SERVER_PORT}"
DEST="${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}"

echo "════════════════════════════════════════════════════════════════════"
echo "  Đồng bộ StreamingTTS lên Server: ${SERVER_USER}@${SERVER_IP}:${SERVER_PORT}"
echo "  Thư mục đích: ${REMOTE_DIR}"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# 1. Tạo trước thư mục đích trên server nếu chưa có
echo "[1/4] Khởi tạo thư mục đích trên server..."
${SSH} "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${REMOTE_DIR}/models ${REMOTE_DIR}/voices"

# 2. Đồng bộ code, Dockerfile, requirements và script chạy
#    --delete: xoá trên server các file đã bị xoá/đổi tên ở Mac (chỉ trong
#    app/ config/ engines/ text_normalizer/, không đụng models/ voices/ logs/)
echo "[2/4] Đồng bộ mã nguồn và scripts lên server..."
rsync -avz --delete --progress \
    -e "${SSH}" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".DS_Store" \
    "${LOCAL_DIR}/app" \
    "${LOCAL_DIR}/config" \
    "${LOCAL_DIR}/engines" \
    "${LOCAL_DIR}/text_normalizer" \
    "${LOCAL_DIR}/Dockerfile" \
    "${LOCAL_DIR}/.dockerignore" \
    "${LOCAL_DIR}/requirements.txt" \
    "${LOCAL_DIR}/constraints.txt" \
    "${LOCAL_DIR}/run.sh" \
    "${LOCAL_DIR}/README.md" \
    "${DEST}/"

# 3. Đồng bộ voices (file mẫu clone giọng .wav + .txt)
echo "[3/4] Đồng bộ thư mục voices lên server..."
rsync -avz --delete --progress \
    -e "${SSH}" \
    --exclude ".DS_Store" \
    "${LOCAL_DIR}/voices/" \
    "${DEST}/voices/"

# 4. Đồng bộ models: viettts (OmniVoice fine-tune VI ~3.2GB), engtts (OmniVoice
#    pretrained ~3.2GB), normalizer (CRF ~4MB). rsync chỉ gửi phần thay đổi.
echo "[4/4] Đồng bộ models (viettts, engtts, normalizer) lên server..."
rsync -avz --progress \
    -e "${SSH}" \
    --exclude ".DS_Store" \
    --exclude ".cache" \
    "${LOCAL_DIR}/models/viettts" \
    "${LOCAL_DIR}/models/engtts" \
    "${LOCAL_DIR}/models/normalizer" \
    "${DEST}/models/"

${SSH} "${SERVER_USER}@${SERVER_IP}" "chmod +x ${REMOTE_DIR}/run.sh"

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "✅ ĐỒNG BỘ HOÀN TẤT LÊN SERVER!"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Khởi chạy trên server:"
echo "  cd ${REMOTE_DIR} && ./run.sh        # container 'streamingtts', GPU 0, cổng 13128"
echo ""
echo "Kiểm tra từ máy Mac:"
echo "  ./test_13128.sh"
echo "  Swagger UI: http://${SERVER_IP}:13128/docs"
echo "════════════════════════════════════════════════════════════════════"
