#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Script test StreamingTTS (Port 13128)
#
# Cách dùng:
#   ./test_13128.sh                                                # Test mặc định (north)
#   ./test_13128.sh "The oyster has a beautiful pearl." north      # Tiếng Anh giọng north
#   ./test_13128.sh "The oyster has a beautiful pearl." south      # Tiếng Anh giọng south
#   ./test_13128.sh "Hôm nay thời tiết Hà Nội rất đẹp." north      # Tiếng Việt giọng Bắc
#   ./test_13128.sh "Hôm nay thời tiết Sài Gòn rất đẹp." south     # Tiếng Việt giọng Nam
#   ./test_13128.sh "Hello world" en_north                         # Tiếng Anh chỉ định rõ
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

BASE_URL="${BASE_URL:-http://192.168.91.176:13128}"
API_KEY="${TTS_API_KEY:-ioit2025}"
CURL_TIMEOUT="${CURL_TIMEOUT:-180}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"

DEFAULT_TEXT="$(cat <<'EOF'
The oyster has a beautiful pearl.
EOF
)"
TEXT="${1:-$DEFAULT_TEXT}"
VOICE="${2:-north}"
OUT="${3:-tts_13128_$(date +%Y%m%d_%H%M%S).wav}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

require_cmd curl
require_cmd python3

echo "════════════════════════════════════════════════════════════════════"
echo "  Testing StreamingTTS Endpoint: $BASE_URL"
echo "  Voice: $VOICE"
echo "════════════════════════════════════════════════════════════════════"

echo "Checking health: $BASE_URL/health"
if ! curl -fsS --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time 15 "$BASE_URL/health"; then
  echo
  echo "❌ Health check failed. Make sure StreamingTTS is running on port 13128." >&2
  echo "Example:" >&2
  echo "  BASE_URL=http://192.168.91.176:13128 ./test_13128.sh" >&2
  exit 1
fi
echo ""
echo "🚀 Generating audio on port 13128 (StreamingTTS)..."
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

voice = os.environ["VOICE"]
text = os.environ["TEXT"]

# Detect model:
if voice.startswith("en") or voice.startswith("english") or voice.endswith("_en"):
    model = "EngTTS"
elif voice.startswith("vi") or voice.startswith("vietnamese") or voice.endswith("_vi"):
    model = "VietTTS"
else:
    # "north", "south", "ai_calling": if text contains Vietnamese accents, use VietTTS, else EngTTS
    is_vi = any(c in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ" for c in text.lower())
    model = "VietTTS" if is_vi else "EngTTS"

payload = {
    "model": model,
    "input": text,
    "voice": voice,
    "response_format": "wav",
    "speed": 1.0,
}
print(json.dumps(payload, ensure_ascii=False))
PY
)"

echo "✅ Saved audio to: $OUT"

if command -v afplay >/dev/null 2>&1; then
  echo "🔊 Playing audio..."
  afplay "$OUT"
fi
