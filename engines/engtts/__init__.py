"""Public facade for the English TTS engine (OmniVoice pretrained).

Uses the official un-finetuned k2-fsa/OmniVoice checkpoint for native,
natural English pronunciation and zero-shot voice cloning.

    from engines.engtts import EngTTSEngine
    eng = EngTTSEngine(model_dir, device="cuda:1")
    eng.load()
    eng.register_voice("en_female", ref_audio="...wav", ref_text_file="...txt")
    audio = eng.synthesize("Hello world.", voice="en_female")
"""
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _install_aliases():
    """Ensure backend classes recognize VietTTS and OmniVoice configs."""
    from omnivoice.models.omnivoice import (
        OmniVoice as _BackendModel,
        OmniVoiceConfig as _BackendConfig,
    )
    from transformers.models.higgs_audio_v2_tokenizer.configuration_higgs_audio_v2_tokenizer import (
        HiggsAudioV2TokenizerConfig as _AudioTokConfig,
    )
    from transformers.models.higgs_audio_v2_tokenizer.modeling_higgs_audio_v2_tokenizer import (
        HiggsAudioV2TokenizerModel as _AudioTokModel,
    )

    _BackendModel.__name__   = "VietTTS"
    _BackendConfig.model_type = "viettts"
    _AudioTokModel.__name__   = "VietTTSAudioTokenizer"
    _AudioTokConfig.model_type = "viettts_audio_tokenizer"

    return _BackendModel


class EngTTSEngine:
    """English voice-cloning TTS engine powered by OmniVoice pretrained weights.

    Parameters
    ----------
    model_dir : Path | str
        Local directory containing the model weights + tokenizer + audio_tokenizer/.
    device : str
        Torch device string ("cuda:1", "cpu", ...).
    num_step : int
        Diffusion steps for normal inputs (high-quality).
    num_step_long : int
        Diffusion steps for long inputs.
    num_step_short : int
        Diffusion steps for ultra-short inputs.
    """
    SAMPLE_RATE = 24_000

    def __init__(
        self,
        model_dir,
        device: str = "cuda:1",
        num_step: int = 46,
        num_step_long: int = 46,
        num_step_short: int = 14,
        short_threshold: int = 7,
        long_threshold: int = 50,
        audio_chunk_duration: float = 10.0,
        audio_chunk_threshold: float = 15.0,
        torch_compile: bool = False,
    ):
        self._model_dir = str(model_dir)
        self._device = device
        self._num_step = num_step
        self._num_step_long = num_step_long
        self._num_step_short = num_step_short
        self._short_threshold = short_threshold
        self._long_threshold = long_threshold
        self._audio_chunk_duration = audio_chunk_duration
        self._audio_chunk_threshold = audio_chunk_threshold
        self._torch_compile = torch_compile
        self._model = None
        self._voice_prompts: dict = {}

    def load(self) -> None:
        """Load English OmniVoice weights into VRAM."""
        if self._model is not None:
            return
        import torch
        ModelClass = _install_aliases()
        logger.info("EngTTS (OmniVoice): loading weights from %s on %s", self._model_dir, self._device)
        self._model = ModelClass.from_pretrained(
            self._model_dir,
            device_map=self._device,
            dtype=torch.float16,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("EngTTS (OmniVoice): loaded on %s", self._device)

    def register_voice(self, name: str, ref_audio, ref_text_file) -> None:
        """Cache a voice-clone prompt under `name`. Call after load()."""
        ref_audio = Path(ref_audio)
        ref_text_file = Path(ref_text_file)
        if not ref_audio.is_file():
            alt_audio = ref_audio.with_suffix(".wav") if ref_audio.suffix != ".wav" else ref_audio.with_suffix(".mp3")
            if alt_audio.is_file():
                ref_audio = alt_audio
        if not (ref_audio.is_file() and ref_text_file.is_file()):
            logger.warning("EngTTS: voice %r refs missing (%s, %s) — skipped",
                           name, ref_audio, ref_text_file)
            return
        with open(ref_text_file, "r", encoding="utf-8") as f:
            ref_text = f.read().strip()
        if self._model is None:
            raise RuntimeError("EngTTSEngine.load() must be called before register_voice()")
        import torch
        with torch.inference_mode():
            self._voice_prompts[name] = self._model.create_voice_clone_prompt(
                ref_audio=str(ref_audio), ref_text=ref_text,
            )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("EngTTS: cached voice prompt %r from %s", name, ref_audio.name)

    def warmup(self) -> None:
        """Lightweight warmup pass with English text."""
        if self._model is None:
            return
        import torch
        with torch.inference_mode():
            try:
                self._model.generate(text="Hello.", language="english", num_step=8)
            except Exception as exc:
                logger.warning("EngTTS: warmup failed: %s", exc)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: str = "english",
        num_step: Optional[int] = None,
    ) -> np.ndarray:
        """Generate 24 kHz mono float32 audio for `text` in English."""
        if self._model is None:
            raise RuntimeError("EngTTSEngine.load() must be called before synthesize()")
        prompt = self._voice_prompts.get(voice) if voice else None

        if num_step is None:
            clean_len = len(text.strip().rstrip(".!?。！？;:,"))
            if clean_len <= self._short_threshold:
                num_step = self._num_step_short
            elif len(text) > self._long_threshold:
                num_step = self._num_step_long
            else:
                num_step = self._num_step

        kwargs: dict = {
            "language": language,
            "num_step": num_step,
            "guidance_scale": 2.0,
            "audio_chunk_duration": self._audio_chunk_duration,
            "audio_chunk_threshold": self._audio_chunk_threshold,
        }
        if prompt is not None:
            kwargs["voice_clone_prompt"] = prompt
        else:
            kwargs["instruct"] = "female, young adult"

        audio_list = self._model.generate(text=text, **kwargs)
        if not audio_list or len(audio_list[0]) == 0:
            return np.array([], dtype=np.float32)
        return audio_list[0].astype(np.float32)


__all__ = ["EngTTSEngine"]
