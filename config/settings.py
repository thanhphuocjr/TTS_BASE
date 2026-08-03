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
PORT           = int(os.environ.get("TTS_PORT", "13125"))
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

# ---- VietTTS engine knobs -------------------------------------------------
VIETTTS_SAMPLE_RATE = 24_000
# Diffusion steps. Short inputs use the high-quality `NUM_STEP` value; long
# inputs fall back to `NUM_STEP_LONG` (fewer steps → faster) since the LM
# backbone forward pass already dominates total latency on long inputs.
VIETTTS_NUM_STEP        = int(os.environ.get("TTS_VIETTTS_NUM_STEP", "24"))
VIETTTS_NUM_STEP_LONG   = int(os.environ.get("TTS_VIETTTS_NUM_STEP_LONG", "32"))
VIETTTS_LONG_THRESHOLD  = int(os.environ.get("TTS_VIETTTS_LONG_THRESHOLD", "50"))
VIETTTS_TEMPO           = float(os.environ.get("TTS_VIETTTS_TEMPO", "0.95"))
OUTPUT_PEAK_DBFS        = float(os.environ.get("TTS_OUTPUT_PEAK_DBFS", "-1.0"))
VIETTTS_DEVICE          = os.environ.get("TTS_VIETTTS_DEVICE", "cuda:1")
# Off by default — known to cause Vietnamese→English drift mid-utterance on
# some inputs. Set TTS_VIETTTS_TORCH_COMPILE=1 to opt in (3× speedup if stable).
VIETTTS_TORCH_COMPILE   = os.environ.get("TTS_VIETTTS_TORCH_COMPILE", "0") == "1"

# ---- EngTTS engine knobs --------------------------------------------------
ENGTTS_SAMPLE_RATE = 24_000

# ---- Voice catalogue ------------------------------------------------------
# Maps the OpenAI-style voice id -> engine routing.
VOICE_MAP = {
    "vi_fe": {"engine": "viettts", "gender": "female", "voice_change": None,   "model": "VietTTS"},
    "vi_ma": {"engine": "viettts", "gender": "male",   "voice_change": None,   "model": "VietTTS"},
    "en_fe": {"engine": "engtts",  "voice": "af_heart","voice_change": "girl", "model": "EngTTS"},
    "en_ma": {"engine": "engtts",  "voice": "am_puck", "voice_change": "boy",  "model": "EngTTS"},
}

MODEL_MAP = {
    "VietTTS": "viettts",
    "EngTTS":  "engtts",
}

# ---- Misc / external tools -----------------------------------------------
SOX_PATH = shutil.which("sox")
LOG_RETENTION_DAYS = 30
TIMEZONE_OFFSET_HOURS = 7  # UTC+7 (Asia/Ho_Chi_Minh)
