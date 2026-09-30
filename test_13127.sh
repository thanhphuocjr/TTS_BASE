#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://192.168.91.176:13127}"
API_KEY="${TTS_API_KEY:-ioit2025}"
CURL_TIMEOUT="${CURL_TIMEOUT:-180}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"

DEFAULT_TEXT="$(cat <<'EOF'
Success is not something that happens overnight; it is the result of continuous effort, dedication, and resilience. Life will always throw challenges in your path, but it is your ability to stand up after every fall that truly defines your future. When you pursue a big dream, remember that even the smallest step forward is still progress, and as long as you never give up, you will eventually reach your destination.
EOF
)"
TEXT="${1:-$DEFAULT_TEXT}"
VOICE="${2:-en_fe}"
OUT="${3:-tts_13127_$(date +%Y%m%d_%H%M%S).wav}"

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
  echo "  BASE_URL=http://192.168.91.176:13127 ./test_13127.sh" >&2
  exit 1
fi
echo
echo "Generating audio on port 13127..."
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
