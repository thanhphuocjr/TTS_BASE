"""Text preparation helpers for TTS-friendly Vietnamese prompts."""

from __future__ import annotations

import re


_ALL_CAPS_WORD_RE = re.compile(
    r"\b[A-ZĐƯƠÂÊÔĂÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆ"
    r"ÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ]{2,}\b"
)


def _lower_all_caps(match: re.Match) -> str:
    return match.group(0).lower()


def sanitize_tts_text(text: str) -> str:
    """Keep base text behavior, only lowering all-caps Vietnamese words."""
    return _ALL_CAPS_WORD_RE.sub(_lower_all_caps, text.strip())


__all__ = ["sanitize_tts_text"]
