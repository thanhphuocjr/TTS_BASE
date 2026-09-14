#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://192.168.91.240:13125}"
API_KEY="${TTS_API_KEY:-ioit2025}"
CURL_TIMEOUT="${CURL_TIMEOUT:-180}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"

DEFAULT_TEXT="$(cat <<'EOF'
Trong bối cảnh nền kinh tế số toàn cầu đang trải qua những bước chuyển mình vô cùng mạnh mẽ và sâu sắc dưới sự tác động trực tiếp của cuộc cách mạng công nghiệp lần thứ tư, việc nghiên cứu, phát triển và ứng dụng thực tiễn các hệ thống trí tuệ nhân tạo, đặc biệt là các mô hình học máy chuyên sâu trong lĩnh vực xử lý ngôn ngữ tự nhiên và chuyển đổi văn bản thành giọng nói tiếng Việt, không chỉ đòi hỏi sự đầu tư vượt trội về cơ sở hạ tầng phần cứng với các hệ thống máy chủ GPU hiệu năng cao mà còn yêu cầu một tư duy tối ưu hóa thuật toán cực kỳ linh hoạt để giải quyết triệt để các bài toán kỹ thuật phức tạp liên quan đến độ trễ hệ thống, hiện tượng nhiễu âm nền, lỗi mất chữ ở cuối phân đoạn dài hoặc tình trạng giọng đọc bị biến đổi âm sắc một cách bất thường khi xử lý các chuỗi văn bản có mật độ từ vựng chuyên ngành dày đặc từ kinh tế, tài chính, y học cho đến công nghệ thông tin như blockchain, học sâu, điện toán đám mây và dữ liệu lớn.
EOF
)"
TEXT="${1:-$DEFAULT_TEXT}"
VOICE="${2:-vi_fe}"
OUT="${3:-tts_13125_$(date +%Y%m%d_%H%M%S).wav}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

require_cmd curl
require_cmd python3

echo "Checking health: $BASE_URL/health"
if ! curl -fsS --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time 15 "$BASE_URL/health"; then
  echo
  echo "Health check failed. Make sure the TTS server is running and BASE_URL is correct." >&2
  echo "Example:" >&2
  echo "  BASE_URL=http://192.168.91.240:13125 ./test_13125.sh" >&2
  exit 1
fi
echo
echo "Generating audio..."
echo "Voice: $VOICE"
echo "Output: $OUT"

export TEXT VOICE

curl -fsS --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time "$CURL_TIMEOUT" \
  -X POST "$BASE_URL/v1/audio/speech" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -o "$OUT" \
  -d "$(python3 - <<'PY'
import json
import os

payload = {
    "model": "VietTTS",
    "input": os.environ["TEXT"],
    "voice": os.environ["VOICE"],
    "response_format": "wav",
    "speed": 1.0,
}
print(json.dumps(payload, ensure_ascii=False))
PY
)"

echo "Saved audio to: $OUT"

if command -v afplay >/dev/null 2>&1; then
  echo "Playing audio..."
  afplay "$OUT"
fi
