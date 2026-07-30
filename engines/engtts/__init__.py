"""Public facade for the English TTS engine.

Hides the underlying inference backend behind a single class.

    from engines.engtts import EngTTSEngine
    eng = EngTTSEngine(model_dir)
    eng.load(warmup_voices=["af_heart", "am_puck"])
    audio = eng.synthesize("Hello.", voice="af_heart")
"""
import logging
from pathlib import Path
from typing import Iterable

import numpy as np

logger = logging.getLogger(__name__)


class EngTTSEngine:
    """English TTS engine.

    Parameters
    ----------
    model_dir : Path | str
        Local directory containing the model weights (*.pth), a `voices/`
        subdirectory of voice packs (*.pt), and a `config.json`.
    """
    SAMPLE_RATE = 24_000

    def __init__(self, model_dir):
        self._model_dir = str(model_dir)
        self._pipeline = None

    def load(self, warmup_voices: Iterable[str] = ()) -> None:
        """Initialize the pipeline from on-disk weights. Optionally warm up voices."""
        if self._pipeline is not None:
            return
        import torch
        from kokoro import KModel as _BackendModel, KPipeline as _BackendPipeline
        logger.info("EngTTS: loading weights from %s", self._model_dir)

        model_dir = Path(self._model_dir)
        config_path = model_dir / "config.json"
        weights = next(model_dir.glob("*.pth"))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # repo_id below is purely a label — `config` + `model` are local paths
        # so no network call is made.
        backend_model = _BackendModel(
            repo_id="EngTTS",
            config=str(config_path),
            model=str(weights),
        ).to(device).eval()

        self._pipeline = _BackendPipeline(
            lang_code="a", repo_id="EngTTS", model=backend_model,
        )
        # Pre-load every voice pack from local so no network lookup ever fires.
        voices_dir = model_dir / "voices"
        if voices_dir.is_dir():
            for vp in voices_dir.glob("*.pt"):
                self._pipeline.voices[vp.stem] = torch.load(vp, weights_only=True)
            logger.info("EngTTS: preloaded %d voice packs", len(self._pipeline.voices))

        for voice in warmup_voices:
            try:
                for _ in self._pipeline("Hello.", voice=voice, speed=1):
                    pass
                logger.info("EngTTS: warmed voice %r", voice)
            except Exception as exc:
                logger.warning("EngTTS: warmup of %r failed: %s", voice, exc)
        logger.info("EngTTS: ready")

    def synthesize(self, text: str, voice: str) -> np.ndarray:
        """Generate 24 kHz mono float32 audio for `text` using `voice`."""
        if self._pipeline is None:
            raise RuntimeError("EngTTSEngine.load() must be called before synthesize()")
        chunks = []
        for _, _, audio in self._pipeline(text, voice=voice, speed=1):
            if audio is not None:
                chunks.append(audio.numpy())
        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks)


__all__ = ["EngTTSEngine"]
