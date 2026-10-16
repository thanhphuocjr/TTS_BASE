"""Central settings. All values may be overridden via environment variables.

Paths default to the on-disk layout shipped in the Docker image.
"""
import os
import shutil
from pathlib import Path

# Project root (StreamingTTS/)
ROOT = Path(__file__).resolve().parent.parent

# ---- API / server ---------------------------------------------------------
API_KEY        = os.environ.get("TTS_API_KEY", "ioit2025")
HOST           = os.environ.get("TTS_HOST", "0.0.0.0")
PORT           = int(os.environ.get("TTS_PORT", "13128"))
MAX_WORKERS    = int(os.environ.get("TTS_MAX_WORKERS", "1"))
OUTPUT_SR      = int(os.environ.get("TTS_OUTPUT_SR", "24000"))

# ---- Engine paths (baked into image) -------------------------------------
MODELS_DIR     = Path(os.environ.get("TTS_MODELS_DIR", str(ROOT / "models")))
VOICES_DIR     = Path(os.environ.get("TTS_VOICES_DIR", str(ROOT / "voices")))
PRESETS_DIR    = Path(os.environ.get("TTS_PRESETS_DIR", str(ROOT / "presets")))
LOGS_DIR       = Path(os.environ.get("TTS_LOGS_DIR", str(ROOT / "logs")))

VIETTTS_MODEL_DIR    = MODELS_DIR / "viettts"
ENGTTS_MODEL_DIR     = MODELS_DIR / "engtts"
NORMALIZER_MODEL_DIR = MODELS_DIR / "normalizer"

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# ---- VietTTS engine knobs -------------------------------------------------
VIETTTS_SAMPLE_RATE = 24_000
# Diffusion steps:
# - Ultra-short inputs (letters or short words <= SHORT_THRESHOLD chars) use
#   `NUM_STEP_SHORT` (12-16 steps) for fast synthesis (~100ms per letter).
# - Normal inputs use the high-quality `NUM_STEP` value (46 steps).
# - Long inputs fall back to `NUM_STEP_LONG` (46 steps) since the LM
#   backbone forward pass already dominates total latency on long inputs.
VIETTTS_NUM_STEP_SHORT  = int(os.environ.get("TTS_VIETTTS_NUM_STEP_SHORT", "14"))
VIETTTS_SHORT_THRESHOLD = int(os.environ.get("TTS_VIETTTS_SHORT_THRESHOLD", "8"))
VIETTTS_NUM_STEP        = int(os.environ.get("TTS_VIETTTS_NUM_STEP", "46"))
VIETTTS_NUM_STEP_LONG   = int(os.environ.get("TTS_VIETTTS_NUM_STEP_LONG", "46"))
VIETTTS_LONG_THRESHOLD  = int(os.environ.get("TTS_VIETTTS_LONG_THRESHOLD", "50"))
# OmniVoice long-form generation. Start chunking once the estimated output is
# longer than the threshold and keep each generated chunk near the configured
# duration. Shorter chunks reduce pronunciation/prosody drift on long passages.
VIETTTS_AUDIO_CHUNK_DURATION  = float(
    os.environ.get("TTS_VIETTTS_AUDIO_CHUNK_DURATION", "10.0")
)
VIETTTS_AUDIO_CHUNK_THRESHOLD = float(
    os.environ.get("TTS_VIETTTS_AUDIO_CHUNK_THRESHOLD", "15.0")
)
VIETTTS_TEMPO           = float(os.environ.get("TTS_VIETTTS_TEMPO", "1.1"))
COLON_PAUSE_SECONDS     = float(os.environ.get("TTS_COLON_PAUSE_SECONDS", "0.2"))
ELLIPSIS_PAUSE_SECONDS  = float(os.environ.get("TTS_ELLIPSIS_PAUSE_SECONDS", "0.4"))
OUTPUT_PEAK_DBFS        = float(os.environ.get("TTS_OUTPUT_PEAK_DBFS", "-1.0"))
DEFAULT_DEVICE          = os.environ.get("TTS_DEVICE", "cuda:0")
VIETTTS_DEVICE          = os.environ.get("TTS_VIETTTS_DEVICE", DEFAULT_DEVICE)
# Off by default — known to cause Vietnamese→English drift mid-utterance on
# some inputs. Set TTS_VIETTTS_TORCH_COMPILE=1 to opt in (3× speedup if stable).
VIETTTS_TORCH_COMPILE   = os.environ.get("TTS_VIETTTS_TORCH_COMPILE", "0") == "1"

# ---- EngTTS engine knobs (OmniVoice pretrained) ---------------------------
ENGTTS_SAMPLE_RATE      = 24_000
ENGTTS_DEVICE           = os.environ.get("TTS_ENGTTS_DEVICE", VIETTTS_DEVICE)
ENGTTS_NUM_STEP_SHORT   = int(os.environ.get("TTS_ENGTTS_NUM_STEP_SHORT", "14"))
ENGTTS_SHORT_THRESHOLD  = int(os.environ.get("TTS_ENGTTS_SHORT_THRESHOLD", "8"))
ENGTTS_NUM_STEP         = int(os.environ.get("TTS_ENGTTS_NUM_STEP", "46"))
ENGTTS_NUM_STEP_LONG    = int(os.environ.get("TTS_ENGTTS_NUM_STEP_LONG", "46"))
ENGTTS_LONG_THRESHOLD   = int(os.environ.get("TTS_ENGTTS_LONG_THRESHOLD", "50"))
ENGTTS_AUDIO_CHUNK_DURATION  = float(
    os.environ.get("TTS_ENGTTS_AUDIO_CHUNK_DURATION", "10.0")
)
ENGTTS_AUDIO_CHUNK_THRESHOLD = float(
    os.environ.get("TTS_ENGTTS_AUDIO_CHUNK_THRESHOLD", "15.0")
)
ENGTTS_TORCH_COMPILE    = os.environ.get("TTS_ENGTTS_TORCH_COMPILE", "0") == "1"
ENGTTS_VOLUME_BOOST     = float(os.environ.get("TTS_ENGTTS_VOLUME_BOOST", "1.5"))
VIETTTS_VOLUME_BOOST    = float(os.environ.get("TTS_VIETTTS_VOLUME_BOOST", "1.0"))

# ---- Voice catalogue ------------------------------------------------------
# Dual OmniVoice:
#   VietTTS = OmniVoice finetuned on Vietnamese dataset (voices: north, south, vi_north, vi_south)
#   EngTTS  = OmniVoice official pretrained from k2-fsa (voices: en_north, en_south)
VOICE_MAP = {
    # Giọng Bắc và Nam chuẩn hóa
    "north": {
        "engine": "viettts",
        "voice": "vietnamese_north",
        "region": "north",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "south": {
        "engine": "viettts",
        "voice": "vietnamese_south",
        "region": "south",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    # Tiếng Việt có prefix
    "vi_north": {
        "engine": "viettts",
        "voice": "vietnamese_north",
        "region": "north",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "vi_south": {
        "engine": "viettts",
        "voice": "vietnamese_south",
        "region": "south",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "vietnamese_north": {
        "engine": "viettts",
        "voice": "vietnamese_north",
        "region": "north",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "vietnamese_south": {
        "engine": "viettts",
        "voice": "vietnamese_south",
        "region": "south",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    # Tiếng Anh
    "en_north": {
        "engine": "engtts",
        "voice": "english_north",
        "region": "north",
        "language": "english",
        "model": "EngTTS",
    },
    "en_south": {
        "engine": "engtts",
        "voice": "english_south",
        "region": "south",
        "language": "english",
        "model": "EngTTS",
    },
    "english_north": {
        "engine": "engtts",
        "voice": "english_north",
        "region": "north",
        "language": "english",
        "model": "EngTTS",
    },
    "english_south": {
        "engine": "engtts",
        "voice": "english_south",
        "region": "south",
        "language": "english",
        "model": "EngTTS",
    },
    # Backward compatibility aliases
    "vi_fe": {
        "engine": "viettts",
        "voice": "vietnamese_south",
        "region": "south",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "vi_ma": {
        "engine": "viettts",
        "voice": "vietnamese_north",
        "region": "north",
        "language": "vietnamese",
        "model": "VietTTS",
    },
    "en_fe": {
        "engine": "engtts",
        "voice": "english_south",
        "region": "south",
        "language": "english",
        "model": "EngTTS",
    },
    "en_ma": {
        "engine": "engtts",
        "voice": "english_north",
        "region": "north",
        "language": "english",
        "model": "EngTTS",
    },
}

MODEL_MAP = {
    "VietTTS": "viettts",
    "EngTTS":  "engtts",
}

# ---- Misc / external tools -----------------------------------------------
SOX_PATH = shutil.which("sox")
LOG_RETENTION_DAYS = 30
TIMEZONE_OFFSET_HOURS = 7  # UTC+7 (Asia/Ho_Chi_Minh)
