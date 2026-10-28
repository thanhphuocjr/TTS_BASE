"""Audio post-processing: tempo adjust, loudness, WAV/PCM encoding, transcoding.

Tempo is shelled out to sox, transcoding to ffmpeg. Functions accept mono
float32 numpy arrays at the engine's sample rate.
"""
import io
import os
import struct
import subprocess
import tempfile

import numpy as np

from config.settings import OUTPUT_SR, SOX_PATH


# ---- Shelled-out sox -----------------------------------------------------
def _run_sox(args: list) -> None:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"sox failed: {proc.stderr.strip()}")


def sox_tempo(audio: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Adjust speech tempo without changing pitch via `sox tempo`.
    factor < 1.0 = slower, > 1.0 = faster.
    """
    if factor == 1.0:
        return audio
    if SOX_PATH is None:
        raise RuntimeError("sox not found")
    import soundfile as sf
    fd_in, path_in = tempfile.mkstemp(suffix=".wav")
    fd_out, path_out = tempfile.mkstemp(suffix=".wav")
    os.close(fd_in); os.close(fd_out)
    try:
        sf.write(path_in, audio, sr, subtype="PCM_16")
        _run_sox([SOX_PATH, path_in, path_out, "tempo", "-s", str(factor)])
        out, _ = sf.read(path_out, dtype="float32")
        return out
    finally:
        for p in (path_in, path_out):
            try: os.unlink(p)
            except OSError: pass


# ---- WAV / PCM encoding --------------------------------------------------
def to_wav_bytes(audio: np.ndarray, sr: int = OUTPUT_SR) -> bytes:
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32_767).astype(np.int16).tobytes()
    data_size = len(pcm)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm)
    return buf.getvalue()


def to_pcm_bytes(audio: np.ndarray) -> bytes:
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32_767).astype(np.int16).tobytes()


def limit_peak(audio: np.ndarray, target_dbfs: float = -1.0) -> np.ndarray:
    """Attenuate hot output so WAV/PCM encoding does not clip."""
    if len(audio) == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    target = float(10 ** (target_dbfs / 20.0))
    if peak > target > 0:
        return (audio * (target / peak)).astype(np.float32)
    return audio.astype(np.float32, copy=False)


def boost_loudness(audio: np.ndarray, gain: float = 1.4) -> np.ndarray:
    """Boost perceived loudness (RMS) via soft saturation tanh without clipping."""
    if len(audio) == 0 or gain <= 1.0:
        return audio
    tanh_gain = float(np.tanh(gain))
    boosted = np.tanh(audio * gain) / tanh_gain
    return boosted.astype(np.float32)


def transcode_wav(wav_bytes: bytes, fmt: str) -> bytes:
    """Re-encode WAV bytes into mp3/opus/aac/flac via ffmpeg."""
    fd_in, path_in = tempfile.mkstemp(suffix=".wav")
    fd_out, path_out = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd_in); os.close(fd_out)
    try:
        with open(path_in, "wb") as f:
            f.write(wav_bytes)
        fmt_map = {"mp3": "mp3", "opus": "opus", "aac": "adts", "flac": "flac"}
        ffmpeg_fmt = fmt_map.get(fmt, fmt)
        subprocess.run(
            ["ffmpeg", "-y", "-i", path_in, "-f", ffmpeg_fmt, path_out],
            capture_output=True, check=True, timeout=30,
        )
        with open(path_out, "rb") as f:
            return f.read()
    finally:
        for p in (path_in, path_out):
            try: os.unlink(p)
            except OSError: pass
