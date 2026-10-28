#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Build + chạy container StreamingTTS trên server
#
# Cách dùng (trong ~/Desktop/Ominivoice-TTS):
#   ./run.sh                      # GPU 0, cổng 13128
#   ./run.sh 1                    # GPU 1
#   HOST_PORT=13129 ./run.sh 1    # cổng khác (vd. chạy thử song song)
#
# Rollback về image của lần build trước:
#   docker tag streamingtts:previous streamingtts:latest && SKIP_BUILD=1 ./run.sh
#
# Model được đóng gói VÀO image lúc build (cần ./models/viettts, engtts,
# normalizer trên server khi build; khi chạy không mount gì ngoài logs/).
# ══════════════════════════════════════════════════════════════════════════════

set -e

TARGET_GPU="${1:-${GPU_ID:-0}}"
HOST_PORT="${HOST_PORT:-13128}"
CONTAINER="streamingtts"
IMAGE="streamingtts:latest"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="${MODELS_DIR:-${APP_DIR}/models}"
LOGS_DIR="${LOGS_DIR:-${APP_DIR}/logs}"

echo "════════════════════════════════════════════════════════════════════"
echo "  Khởi động StreamingTTS"
echo "  Container: ${CONTAINER} | Image: ${IMAGE}"
echo "  GPU: ${TARGET_GPU} | Cổng: ${HOST_PORT} | Logs: ${LOGS_DIR}"
echo "════════════════════════════════════════════════════════════════════"

mkdir -p "${LOGS_DIR}"
cd "${APP_DIR}"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  # 0. Model phải có trong build context để được COPY vào image
  for d in viettts engtts normalizer; do
    if [ ! -d "${MODELS_DIR}/${d}" ]; then
      echo "❌ Thiếu ${MODELS_DIR}/${d} — chạy ./sync_to_server.sh từ máy Mac trước." >&2
      exit 1
    fi
  done

  OLD_ID="$(docker image inspect -f '{{.Id}}' "${IMAGE}" 2>/dev/null || true)"
  PREV_ID="$(docker image inspect -f '{{.Id}}' streamingtts:previous 2>/dev/null || true)"

  echo "[1/3] Đang build docker image ${IMAGE}..."
  docker build -t "${IMAGE}" .
  NEW_ID="$(docker image inspect -f '{{.Id}}' "${IMAGE}")"

  # Chỉ giữ bản rollback khi build ra image KHÁC bản đang chạy
  if [ -n "${OLD_ID}" ] && [ "${OLD_ID}" != "${NEW_ID}" ]; then
    docker tag "${OLD_ID}" streamingtts:previous
    echo "      Image đã thay đổi → bản cũ được giữ làm streamingtts:previous"
    # Bản rollback cũ hơn nữa giờ không còn tag → xoá cho đỡ tốn ổ đĩa
    # (docker từ chối xoá nếu nó còn tag khác do bạn tự gán, hoặc đang được dùng)
    if [ -n "${PREV_ID}" ] && [ "${PREV_ID}" != "${OLD_ID}" ] && [ "${PREV_ID}" != "${NEW_ID}" ]; then
      docker rmi "${PREV_ID}" >/dev/null 2>&1 || true
    fi
  elif [ -z "${OLD_ID}" ]; then
    echo "      Build lần đầu → chưa có bản rollback"
  else
    echo "      Image không đổi so với bản đang chạy → giữ nguyên streamingtts:previous"
  fi
else
  echo "[1/3] SKIP_BUILD=1 — dùng image ${IMAGE} có sẵn"
fi

echo "[2/3] Dọn dẹp container ${CONTAINER} cũ nếu có..."
docker rm -f "${CONTAINER}" 2>/dev/null || true

# Chỉ cấp đúng 1 GPU cho container -> bên trong container luôn là cuda:0
echo "[3/3] Khởi chạy ${CONTAINER} (GPU ${TARGET_GPU}, cổng ${HOST_PORT})..."
docker run -d \
  --name "${CONTAINER}" \
  --restart unless-stopped \
  --gpus "\"device=${TARGET_GPU}\"" \
  -e TTS_DEVICE="cuda:0" \
  -p "${HOST_PORT}:13128" \
  -v "${LOGS_DIR}:/app/logs" \
  "${IMAGE}"

echo ""
echo "✅ ${CONTAINER} đã khởi động trên cổng ${HOST_PORT} (GPU ${TARGET_GPU})."
echo "Theo dõi log thời gian thực (Ctrl+C để thoát, container vẫn chạy):"
echo "------------------------------------------------------------------"
docker logs -f "${CONTAINER}"
