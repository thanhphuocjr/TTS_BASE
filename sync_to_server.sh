#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Script đồng bộ code StreamingTTS từ Mac lên GPU Server (Phiên bản v8 - Port 13128)
# Server: ai@192.168.91.176 (Port 2225)
# Thư mục đích: ~/Desktop/streamingtts-v8
# ══════════════════════════════════════════════════════════════════════════════

set -e

SERVER_USER="ai"
SERVER_IP="192.168.91.176"
SERVER_PORT="2225"
REMOTE_DIR="~/Desktop/streamingtts-v8"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "════════════════════════════════════════════════════════════════════"
echo "  Đồng bộ StreamingTTS-v8 lên Server: ${SERVER_USER}@${SERVER_IP}:${SERVER_PORT}"
echo "  Thư mục đích: ${REMOTE_DIR}"
echo "  Cấu hình: Port 13128"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# 1. Tạo trước thư mục đích trên server nếu chưa có
echo "[1/4] Khởi tạo thư mục đích trên server..."
ssh -p ${SERVER_PORT} "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${REMOTE_DIR}/models/engtts ${REMOTE_DIR}/voices"

# 2. Đồng bộ code, configs, Dockerfile và các test scripts
echo "[2/4] Đồng bộ mã nguồn và scripts lên server..."
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
    "${LOCAL_DIR}/run_v8.sh" \
    "${LOCAL_DIR}/test_13128.sh" \
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"

# 3. Đồng bộ thư mục voices (audio mẫu english_north, english_south, vietnamese_north, vietnamese_south...)
echo "[3/4] Đồng bộ thư mục voices lên server..."
rsync -avz --delete --progress \
    -e "ssh -p ${SERVER_PORT}" \
    --exclude "__pycache__" \
    --exclude ".DS_Store" \
    "${LOCAL_DIR}/voices/" \
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/voices/"

# 4. Đồng bộ mô hình EngTTS (OmniVoice pretrained bản gốc từ k2-fsa)
echo "[4/4] Đồng bộ mô hình EngTTS (OmniVoice pretrained ~3GB) lên server..."
rsync -avz --progress \
    -e "ssh -p ${SERVER_PORT}" \
    --exclude "__pycache__" \
    --exclude ".DS_Store" \
    "${LOCAL_DIR}/models/engtts/" \
    "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/models/engtts/"

# Cấp quyền thực thi cho các script trên server
ssh -p ${SERVER_PORT} "${SERVER_USER}@${SERVER_IP}" "chmod +x ${REMOTE_DIR}/*.sh"

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "✅ ĐỒNG BỘ HOÀN TẤT LÊN SERVER!"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Để khởi chạy StreamingTTS-v8 trên server, bạn chỉ cần thực hiện 1 trong 2 cách:"
echo ""
echo "👉 Cách 1 (Nhanh nhất - Chạy trực tiếp script run_v8.sh trên server):"
echo "   ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} 'cd ~/Desktop/streamingtts-v8 && ./run_v8.sh'"
echo ""
echo "👉 Cách 2 (Mở terminal trên Server và chạy):"
echo "   cd ~/Desktop/streamingtts-v8"
echo "   ./run_v8.sh"
echo ""
echo "Kiểm tra sau khi khởi chạy:"
echo "  - Test endpoint từ máy Mac: ./test_13128.sh"
echo "  - Swagger UI: http://${SERVER_IP}:13128/docs"
echo "════════════════════════════════════════════════════════════════════"
