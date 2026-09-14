"""Unified TTS Server — OpenAI-compatible API (POST /v1/audio/speech).

Routes are voice-id based:
  voice=vi_fe -> VietTTSEngine, cloned female voice
  voice=vi_ma -> VietTTSEngine, cloned male voice
  voice=en_fe -> EngTTSEngine + girl voice-changer preset
  voice=en_ma -> EngTTSEngine + boy voice-changer preset

Auth: Bearer token via config.settings.API_KEY.
"""
import asyncio
import logging
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from app import csv_logger
from app.audio_post import (
    apply_voice_preset,
    limit_peak,
    sox_tempo,
    to_pcm_bytes,
    to_wav_bytes,
    transcode_wav,
)
from app.auth import require_api_key
from app.schemas import SpeechRequest
from config.settings import (
    COLON_PAUSE_SECONDS,
    ELLIPSIS_PAUSE_SECONDS,
    ENGTTS_MODEL_DIR,
    ENGTTS_SAMPLE_RATE,
    MAX_WORKERS,
    MODEL_MAP,
    NORMALIZER_MODEL_DIR,
    OUTPUT_PEAK_DBFS,
    OUTPUT_SR,
    PORT,
    SOX_PATH,
    VIETTTS_AUDIO_CHUNK_DURATION,
    VIETTTS_AUDIO_CHUNK_THRESHOLD,
    VIETTTS_DEVICE,
    VIETTTS_LONG_THRESHOLD,
    VIETTTS_MODEL_DIR,
    VIETTTS_NUM_STEP,
    VIETTTS_NUM_STEP_LONG,
    VIETTTS_NUM_STEP_SHORT,
    VIETTTS_SHORT_THRESHOLD,
    VIETTTS_TORCH_COMPILE,
    VIETTTS_SAMPLE_RATE,
    VIETTTS_TEMPO,
    VOICE_MAP,
    VOICES_DIR,
)
from engines.engtts import EngTTSEngine
from engines.viettts import VietTTSEngine
from text_normalizer import TextNormalizer

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
csv_logger.init()
logger = logging.getLogger("uvicorn")

_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

_viettts: VietTTSEngine = VietTTSEngine(
    VIETTTS_MODEL_DIR,
    device=VIETTTS_DEVICE,
    num_step=VIETTTS_NUM_STEP,
    num_step_long=VIETTTS_NUM_STEP_LONG,
    num_step_short=VIETTTS_NUM_STEP_SHORT,
    short_threshold=VIETTTS_SHORT_THRESHOLD,
    long_threshold=VIETTTS_LONG_THRESHOLD,
    audio_chunk_duration=VIETTTS_AUDIO_CHUNK_DURATION,
    audio_chunk_threshold=VIETTTS_AUDIO_CHUNK_THRESHOLD,
    torch_compile=VIETTTS_TORCH_COMPILE,
)
_engtts: EngTTSEngine = EngTTSEngine(ENGTTS_MODEL_DIR)
_normalizer: TextNormalizer = TextNormalizer(model_path=str(NORMALIZER_MODEL_DIR))

MIME_MAP = {
    "wav":  "audio/wav",
    "mp3":  "audio/mpeg",
    "opus": "audio/ogg; codecs=opus",
    "pcm":  "audio/pcm",
    "aac":  "audio/aac",
    "flac": "audio/flac",
}

app = FastAPI(title="Unified TTS Server (OpenAI-compatible)")


# ---------------------------------------------------------------------------
# Startup: load both engines + warm the normalizer
# ---------------------------------------------------------------------------
def _load_all() -> None:
    with _lock:
        _viettts.load()
        # Register the two cloned voices from voices/ + the shared transcripts.
        _viettts.register_voice(
            "female",
            ref_audio=VOICES_DIR / "south2.wav",
            ref_text_file=VOICES_DIR / "south2.txt",
        )
        _viettts.register_voice(
            "male",
            ref_audio=VOICES_DIR / "viettts_male_ref.wav",
            ref_text_file=VOICES_DIR / "viettts_male_ref.txt",
        )
        _engtts.load(warmup_voices=("af_heart", "am_puck"))
        _normalizer.warmup()
    logger.info("[tts_server] All models ready")


@app.on_event("startup")
async def _startup() -> None:
    if SOX_PATH is None:
        raise RuntimeError("sox not found. Install: apt install -y sox libsox-fmt-mp3")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _load_all)


# ---------------------------------------------------------------------------
# Per-voice synthesis dispatch
# ---------------------------------------------------------------------------
def _ensure_punctuation(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?。！？;:,":
        text += "."
    return text


PAUSE_TOKEN_RE = re.compile(r"((?:\s*(?:(?<!\d):(?!\/\/)|(?:\.{2,}|\u2026)+)\s*)+)")


def _split_text_with_pauses(
    text: str,
    colon_pause: float,
    ellipsis_pause: float,
) -> list[tuple[str, float]]:
    """Split text by colons and ellipses, associating each non-empty segment with its following pause."""
    tokens = PAUSE_TOKEN_RE.split(text)
    items: list[tuple[str, Optional[str]]] = []

    for i in range(0, len(tokens), 2):
        txt = tokens[i].strip()
        delim = tokens[i + 1] if i + 1 < len(tokens) else None
        if txt:
            items.append((txt, delim))
        elif delim and items:
            prev_txt, prev_delim = items[-1]
            items[-1] = (prev_txt, (prev_delim or "") + delim)

    segments: list[tuple[str, float]] = []
    for idx, (txt, delim) in enumerate(items):
        pause = 0.0
        if idx < len(items) - 1 and delim:
            if "." in delim or "\u2026" in delim:
                pause = ellipsis_pause
            elif ":" in delim:
                pause = colon_pause
        segments.append((txt, pause))
    return segments


def _synthesize_single(
    voice: str,
    text: str,
    speed: float = 1.0,
    num_step: Optional[int] = None,
) -> np.ndarray:
    cfg = VOICE_MAP.get(voice)
    if cfg is None:
        raise ValueError(f"Unknown voice '{voice}'. Available: {list(VOICE_MAP.keys())}")
    text = _ensure_punctuation(text)
    engine = cfg["engine"]

    if engine == "viettts":
        gender = cfg.get("gender", "female")
        voice_name = "male" if gender == "male" else "female"
        audio = _viettts.synthesize(text, voice=voice_name, num_step=num_step)
        # Server default tempo multiplied by client-requested speed.
        effective_tempo = VIETTTS_TEMPO * speed
        if effective_tempo != 1.0 and len(audio) > 0:
            audio = sox_tempo(audio, VIETTTS_SAMPLE_RATE, effective_tempo)
        return audio

    if engine == "engtts":
        audio = _engtts.synthesize(text, voice=cfg["voice"])
        change = cfg.get("voice_change")
        if change and len(audio) > 0:
            audio = apply_voice_preset(audio, ENGTTS_SAMPLE_RATE, change)
        # English engine has no server-default tempo — pass client speed through.
        if speed != 1.0 and len(audio) > 0:
            audio = sox_tempo(audio, ENGTTS_SAMPLE_RATE, speed)
        return audio

    raise ValueError(f"Unknown engine '{engine}' for voice '{voice}'")


def _synthesize(
    voice: str,
    text: str,
    speed: float = 1.0,
    pause_seconds: Optional[float] = None,
    colon_pause_seconds: Optional[float] = None,
    ellipsis_pause_seconds: Optional[float] = None,
    num_step: Optional[int] = None,
) -> np.ndarray:
    """Synthesize speech with physical silence injection at colon (":") and ellipsis ("...") boundaries."""
    c_pause = colon_pause_seconds if colon_pause_seconds is not None else (
        pause_seconds if pause_seconds is not None else COLON_PAUSE_SECONDS
    )
    e_pause = ellipsis_pause_seconds if ellipsis_pause_seconds is not None else (
        pause_seconds if pause_seconds is not None else ELLIPSIS_PAUSE_SECONDS
    )

    segments = _split_text_with_pauses(text, colon_pause=c_pause, ellipsis_pause=e_pause)
    if not segments:
        return np.array([], dtype=np.float32)

    # Fast path: single sentence without pause delimiters
    if len(segments) == 1:
        return _synthesize_single(voice, segments[0][0], speed, num_step=num_step)

    # Physical silence injection between segments
    chunks = []
    for i, (part, pause_dur) in enumerate(segments):
        chunk = _synthesize_single(voice, part, speed, num_step=num_step)
        if len(chunk) > 0:
            # 5ms linear fade at edges to prevent boundary clicks/pops
            fade_len = min(120, len(chunk) // 2)
            if fade_len > 0:
                chunk = chunk.copy()
                chunk[:fade_len] *= np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
                chunk[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)

            chunks.append(chunk)
            if i < len(segments) - 1 and pause_dur > 0:
                silence_samples = int(OUTPUT_SR * max(0.0, pause_dur))
                if silence_samples > 0:
                    chunks.append(np.zeros(silence_samples, dtype=np.float32))

    if not chunks:
        return np.array([], dtype=np.float32)

    return np.concatenate(chunks)



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest, _auth=Depends(require_api_key)):
    received_at = time.time()
    request_id = uuid.uuid4().hex[:8]
    timestamp = csv_logger.now_iso()

    normalized_text = ""
    status_code = 200
    error_msg = ""

    def _finalize(content_len: int = 0) -> None:
        csv_logger.log_request({
            "timestamp":       timestamp,
            "request_id":      request_id,
            "model":           req.model,
            "voice":           req.voice,
            "response_format": req.response_format,
            "input_length":    len(req.input),
            "input_text":      req.input,
            "normalized_text": normalized_text,
            "status_code":     status_code,
            "ttfb_ms":         int((time.time() - received_at) * 1000),
            "output_bytes":    content_len,
            "error":           error_msg,
        })

    try:
        if not req.input.strip():
            status_code, error_msg = 400, "invalid_input: 'input' must not be empty"
            _finalize()
            raise HTTPException(status_code=400, detail={
                "error": {"code": "invalid_input", "message": "'input' must not be empty"}
            })

        if req.voice not in VOICE_MAP:
            status_code, error_msg = 400, f"invalid_voice: '{req.voice}'"
            _finalize()
            raise HTTPException(status_code=400, detail={
                "error": {"code": "invalid_voice",
                          "message": f"Unknown voice '{req.voice}'. Available: {list(VOICE_MAP.keys())}"},
            })

        fmt = req.response_format or "wav"
        if fmt not in MIME_MAP:
            status_code, error_msg = 400, f"invalid_format: '{fmt}'"
            _finalize()
            raise HTTPException(status_code=400, detail={
                "error": {"code": "invalid_format",
                          "message": f"Unsupported format '{fmt}'. Available: {list(MIME_MAP.keys())}"},
            })

        engine = VOICE_MAP[req.voice]["engine"]
        if engine == "viettts":
            normalized_text = _normalizer.normalize(req.input)
        else:
            normalized_text = req.input

        logger.info(f"[{request_id}] === /v1/audio/speech ===")
        logger.info(f"[{request_id}] model={req.model} voice={req.voice} format={fmt}")
        logger.info(f"[{request_id}] input_length={len(req.input)} input_text={req.input!r}")
        logger.info(f"[{request_id}] normalized_text={normalized_text!r}")

        if (
            req.colon_pause_seconds is not None
            or req.ellipsis_pause_seconds is not None
            or req.pause_seconds is not None
            or req.num_step is not None
        ):
            logger.info(
                f"[{request_id}] overrides: colon={req.colon_pause_seconds}s "
                f"ellipsis={req.ellipsis_pause_seconds}s pause={req.pause_seconds}s "
                f"num_step={req.num_step}"
            )

        loop = asyncio.get_running_loop()
        try:
            audio = await loop.run_in_executor(
                _executor,
                _synthesize,
                req.voice,
                normalized_text,
                req.speed,
                req.pause_seconds,
                req.colon_pause_seconds,
                req.ellipsis_pause_seconds,
                req.num_step,
            )
        except Exception as exc:
            status_code, error_msg = 500, f"synthesis_error: {exc}"
            csv_logger.log_error_text(
                f"[{request_id}] synthesis failed:\n{traceback.format_exc()}"
            )
            _finalize()
            raise HTTPException(status_code=500, detail={
                "error": {"code": "synthesis_error", "message": str(exc)}
            })

        if len(audio) == 0:
            status_code, error_msg = 422, "empty_audio"
            _finalize()
            raise HTTPException(status_code=422, detail={
                "error": {"code": "empty_audio",
                          "message": "Could not synthesize audio for the given input"}
            })

        audio = limit_peak(audio, OUTPUT_PEAK_DBFS)

        if fmt == "wav":
            content = to_wav_bytes(audio, OUTPUT_SR)
        elif fmt == "pcm":
            content = to_pcm_bytes(audio)
        else:
            wav_bytes = to_wav_bytes(audio, OUTPUT_SR)
            content = await loop.run_in_executor(_executor, transcode_wav, wav_bytes, fmt)

        output_bytes = len(content)
        ttfb_s = time.time() - received_at
        logger.info(f"[{request_id}] OK ttfb={ttfb_s:.3f}s bytes={output_bytes}")
        _finalize(content_len=output_bytes)

        return Response(
            content=content,
            media_type=MIME_MAP[fmt],
            headers={"Content-Length": str(output_bytes), "X-Request-ID": request_id},
        )

    except HTTPException:
        raise
    except Exception as exc:
        status_code, error_msg = 500, f"unhandled: {exc}"
        csv_logger.log_error_text(
            f"[{request_id}] unhandled exception:\n{traceback.format_exc()}"
        )
        _finalize()
        raise HTTPException(status_code=500, detail={
            "error": {"code": "internal_error", "message": str(exc)}
        })


@app.get("/voices")
async def list_voices():
    voices_by_model: dict = {m: [] for m in MODEL_MAP}
    for vid, cfg in VOICE_MAP.items():
        voices_by_model.setdefault(cfg["model"], []).append(vid)
    return {
        "voices":          list(VOICE_MAP.keys()),
        "models":          list(MODEL_MAP.keys()),
        "voices_by_model": voices_by_model,
        "details":         VOICE_MAP,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "models": list(MODEL_MAP.keys()), "voices": list(VOICE_MAP.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
