"""Public facade for Vietnamese text normalization.

Hides the underlying CRF runtime behind a single class. All callers
import only this:

    from text_normalizer import TextNormalizer
    norm = TextNormalizer()
    norm.warmup()
    out = norm.normalize("Lúc 14:30 ngày 25/12/2024 chi 1.250.000 VND.")
"""
import logging
import os
import re
from typing import Optional

from .rules import (
    ABBREVIATIONS,
    MINUS_BETWEEN_NUMS_RE,
    NORMALIZE_NEEDED_RE,
    PRONUNCIATION_OVERRIDES,
    PUNCT_DECOUPLE_RE,
    apply_symbols,
    expand_times,
    swap_us_to_vi_numbers,
)

logger = logging.getLogger(__name__)


def _pin_backend_to_local(model_path: str) -> None:
    """Force the bundled CRF runtime to read weights from `model_path` instead
    of trying to hit the Hugging Face Hub. Idempotent — safe to call repeatedly.

    Patching only `soe_vinorm.utils.get_model_weights_path` isn't enough:
    other submodules did `from .utils import get_model_weights_path` at module
    load time, capturing a reference to the original function. We have to
    re-bind the name in every module that imported it directly.
    """
    from pathlib import Path
    pinned = Path(model_path)
    _stub = lambda *_a, **_kw: pinned  # type: ignore[assignment]

    from soe_vinorm import utils as _u
    _u.get_model_weights_path = _stub  # type: ignore[assignment]
    try:
        _u.get_model_weights_path.cache_clear()  # type: ignore[attr-defined]
    except AttributeError:
        pass

    # Submodules that captured the function reference via `from .utils import …`.
    for mod_name in ("nsw_detector", "nsw_expander"):
        try:
            mod = __import__(f"soe_vinorm.{mod_name}", fromlist=[mod_name])
            if hasattr(mod, "get_model_weights_path"):
                mod.get_model_weights_path = _stub  # type: ignore[attr-defined]
        except ImportError:
            pass


class TextNormalizer:
    """Vietnamese text normalizer with custom rules layered on a CRF backend.

    The CRF backend is loaded lazily on first call (~700 ms one-time) and
    cached for the lifetime of the instance.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path
        self._inner = None

    def _get_inner(self):
        if self._inner is None:
            # Lazy import: avoid heavy startup cost when only rules are needed.
            if self._model_path is not None:
                _pin_backend_to_local(self._model_path)
            from soe_vinorm import SoeNormalizer as _Backend
            self._inner = _Backend()
        return self._inner

    def warmup(self) -> None:
        """Force CRF backend load + run one normalization to amortize first-call cost."""
        try:
            self.normalize("1 + 2 = 3, ngày 25/12/2024.")
        except Exception as exc:
            logger.warning("normalizer warmup failed: %s", exc)

    def normalize(self, text: str) -> str:
        # 0. Always-on pronunciation overrides.
        for pattern, replacement in PRONUNCIATION_OVERRIDES:
            text = pattern.sub(replacement, text)

        if NORMALIZE_NEEDED_RE.search(text):
            # 1. Abbreviations (TP.HCM, Q.1, sđt, VND, USD, ...).
            for pattern, replacement in ABBREVIATIONS:
                text = pattern.sub(replacement, text)
            # 2. Decouple sentence-ending punctuation from letter tokens so
            #    the heavy normalizer's tokenizer can't absorb them.
            text = PUNCT_DECOUPLE_RE.sub(r" \1", text)
            # 3. Spoken-time expansion (HH:MM[:SS] [am|pm|sáng|...]).
            text = expand_times(text)
            # 4. Minus between digits → " trừ ".
            text = MINUS_BETWEEN_NUMS_RE.sub(" trừ ", text)
            # 5. Swap US -> VI decimal/thousand separators inside number tokens.
            text = swap_us_to_vi_numbers(text)
            # 6. Heavy CRF normalizer (numbers, dates, currency, units, ...).
            try:
                text = self._get_inner().normalize(text)
            except Exception as exc:
                logger.warning("CRF normalize failed: %s", exc)
            # 7. Sweep any residual symbols.
            text = apply_symbols(text)

        return re.sub(r"\s+", " ", text).strip()


__all__ = ["TextNormalizer"]
