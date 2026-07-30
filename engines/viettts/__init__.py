"""Public facade for the Vietnamese TTS engine.

Hides the underlying inference backend behind a single class. Callers do not
import anything from the backend package — only this:

    from engines.viettts import VietTTSEngine
    eng = VietTTSEngine(model_dir, device="cuda:0")
    eng.load()
    eng.register_voice("female", ref_audio="...wav", ref_text_file="...txt")
    audio = eng.synthesize("Xin chào.", voice="female")
"""
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _install_aliases():
    """Rename the upstream backend classes in place so on-disk weights can
    use sanitized names (`VietTTS`, `viettts`, `viettts_audio_tokenizer`).

    Subclassing would lose `sub_configs` inheritance plumbing; renaming class
    attributes on the existing classes is the surgical fix.
    """
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


class VietTTSEngine:
    """Vietnamese voice-cloning TTS engine.

    Parameters
    ----------
    model_dir : Path | str
        Local directory containing the model weights + tokenizer + audio_tokenizer/.
    device : str
        Torch device string ("cuda:0", "cpu", ...).
    num_step : int
        Diffusion steps for short inputs (high-quality).
    num_step_long : int
        Diffusion steps for long inputs (faster — LM forward already dominates).
    long_threshold : int
        Length in characters above which a request is "long" and uses
        `num_step_long`. Defaults to 50.
    """
    SAMPLE_RATE = 24_000

    def __init__(
        self,
        model_dir,
        device: str = "cuda:0",
        num_step: int = 24,
        num_step_long: int = 16,
        long_threshold: int = 50,
        torch_compile: bool = False,
    ):
        self._model_dir = str(model_dir)
        self._device = device
        self._num_step = num_step
        self._num_step_long = num_step_long
        self._long_threshold = long_threshold
        self._torch_compile = torch_compile
        self._model = None
        self._voice_prompts: dict = {}

    def load(self) -> None:
        """Load weights into VRAM. Idempotent."""
        if self._model is not None:
            return
        import torch  # local — heavy import
        VietTTS = _install_aliases()
        logger.info("VietTTS: loading weights from %s", self._model_dir)
        self._model = VietTTS.from_pretrained(
            self._model_dir,
            device_map=self._device,
            dtype=torch.float16,
        )
        # Warmup pass so first real request doesn't pay the JIT cost.
        self._model.generate(text="Xin chào.", language="vietnamese", num_step=8)

        if self._torch_compile:
            # Compile the model graph. KNOWN RISK: at low num_step the model has
            # exhibited Vietnamese -> English language drift mid-utterance. Use
            # `dynamic=True` so the inductor doesn't over-specialize on a fixed
            # sequence length. Off by default — opt in via TTS_VIETTTS_TORCH_COMPILE=1.
            logger.warning(
                "VietTTS: compiling model with torch.compile — first request "
                "after this may pay a 30-60s compile cost"
            )
            os.environ.setdefault(
                "TORCHINDUCTOR_CACHE_DIR",
                str(Path(self._model_dir).parent.parent / ".torch_compile_cache"),
            )
            self._model = torch.compile(
                self._model, mode="reduce-overhead", dynamic=True,
            )
            # Trigger the actual compile with one representative call.
            self._model.generate(
                text="Xin chào, đây là một câu kiểm tra.",
                language="vietnamese",
                num_step=self._num_step,
            )
            logger.info("VietTTS: torch.compile warmup complete")

        logger.info("VietTTS: ready")

    def register_voice(self, name: str, ref_audio, ref_text_file) -> None:
        """Cache a voice-clone prompt under `name`. Call after load()."""
        ref_audio = Path(ref_audio)
        ref_text_file = Path(ref_text_file)
        if not (ref_audio.is_file() and ref_text_file.is_file()):
            logger.warning("VietTTS: voice %r refs missing (%s, %s) — skipped",
                           name, ref_audio, ref_text_file)
            return
        with open(ref_text_file, "r", encoding="utf-8") as f:
            ref_text = f.read().strip()
        if self._model is None:
            raise RuntimeError("VietTTSEngine.load() must be called before register_voice()")
        self._voice_prompts[name] = self._model.create_voice_clone_prompt(
            ref_audio=str(ref_audio), ref_text=ref_text,
        )
        logger.info("VietTTS: cached voice prompt %r from %s", name, ref_audio.name)

    def synthesize(self, text: str, voice: Optional[str] = None) -> np.ndarray:
        """Generate 24 kHz mono float32 audio for `text`.

        If `voice` is registered, uses voice cloning. Otherwise falls back to
        instruct mode with a generic female-adult prompt.
        """
        if self._model is None:
            raise RuntimeError("VietTTSEngine.load() must be called before synthesize()")
        prompt = self._voice_prompts.get(voice) if voice else None
        num_step = (
            self._num_step_long
            if len(text) > self._long_threshold
            else self._num_step
        )
        kwargs: dict = {
            "language": "vietnamese",
            "num_step": num_step,
            "guidance_scale": 2.0,
        }
        if prompt is not None:
            kwargs["voice_clone_prompt"] = prompt
        else:
            kwargs["instruct"] = "female, young adult"

        audio_list = self._model.generate(text=text, **kwargs)
        if not audio_list or len(audio_list[0]) == 0:
            return np.array([], dtype=np.float32)
        return audio_list[0].astype(np.float32)


__all__ = ["VietTTSEngine"]
