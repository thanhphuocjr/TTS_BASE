"""Compiled regex + helper functions for the text normalization pipeline.

The orchestrator (TextNormalizer in __init__.py) calls these in order:
  1. lowercase all-caps emphasis words — always
  2. PRONUNCIATION_OVERRIDES — always
  3. (only if NORMALIZE_NEEDED_RE matches:)
     a. ABBREVIATIONS
     b. punctuation decoupling
     c. expand_times
     d. minus-between-digits -> ' trừ '
     e. swap_us_to_vi_numbers
     f. heavy CRF normalizer
     g. residual SYMBOL_MAP sweep
"""
import re

from .mappings import (
    ABBREVIATIONS_SRC,
    PRONUNCIATION_OVERRIDES_SRC,
    SYMBOL_MAP,
    TIME_SUFFIX_MAP,
)


def _compile(rules_src):
    out = []
    for pattern, ignore_case, replacement in rules_src:
        flags = re.IGNORECASE if ignore_case else 0
        out.append((re.compile(pattern, flags), replacement))
    return out


ABBREVIATIONS         = _compile(ABBREVIATIONS_SRC)
PRONUNCIATION_OVERRIDES = _compile(PRONUNCIATION_OVERRIDES_SRC)

SYMBOL_RE = re.compile("|".join(re.escape(k) for k in SYMBOL_MAP))

# A number token (with US- or VI-style thousands/decimal separators).
NUM_TOKEN_RE = re.compile(r"\d[\d,\.]*\d|\d")

# Minus sign sandwiched between two digits → " trừ ". Outside this context the
# dash is dropped so the heavy normalizer doesn't mis-render it as "đến".
MINUS_BETWEEN_NUMS_RE = re.compile(r"(?<=\d)\s*-\s*(?=\d)")

# Cheap test for "does this text need full normalization?". If false we can
# skip the ~100 ms CRF call entirely.
NORMALIZE_NEEDED_RE = re.compile(
    r"\d|[+\-*/=%$€£₫&@#^]|"
    r"\bTP\.|\bQ\.|\bP\.|\bsđt\b|\bĐH\b|\bCĐ\b",
    re.IGNORECASE,
)

# Time pattern: HH:MM[:SS] optionally followed by am/pm (any case, with/without
# dots) or a Vietnamese suffix word. The am/pm forms exclude a trailing dot so
# sentence-ending periods (e.g. "12:00 pm.") aren't swallowed.
TIME_RE = re.compile(
    r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r"(?:\s+(a\.m|am|p\.m|pm|sáng|chiều|tối|trưa))?"
    r"(?!\w)",
    re.IGNORECASE,
)

# Insert a space between a letter token and trailing punctuation so the heavy
# normalizer's currency/unit tokenizer can't absorb the punctuation.
# "VND." -> "VND ." but "5.25" / "25/12/2024" stay attached (digits still glued).
PUNCT_DECOUPLE_RE = re.compile(r"(?<=[^\W\d_])([.,;!?])")

VI_UPPER = (
    "A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ"
    "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)
ALL_CAPS_WORD_RE = re.compile(rf"\b[{VI_UPPER}]{{2,}}\b")


def lowercase_all_caps_words(text: str) -> str:
    """Lowercase only words that are written fully in uppercase."""
    return ALL_CAPS_WORD_RE.sub(lambda m: m.group(0).lower(), text)


def _int_to_vi(n: int) -> str:
    """Cardinal integer to Vietnamese words. Imported lazily because num2words
    is a sizeable transitive dep."""
    from num2words import num2words
    return num2words(n, lang="vi")


def expand_times(text: str) -> str:
    """Replace HH:MM[:SS] [am/pm] with spoken Vietnamese."""
    def repl(m: re.Match) -> str:
        h, mm, ss, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        h_i, mm_i = int(h), int(mm)
        if not (0 <= h_i <= 23 and 0 <= mm_i <= 59):
            return m.group(0)

        parts = [f"{_int_to_vi(h_i)} giờ"]
        if mm_i != 0:
            parts.append(f"{_int_to_vi(mm_i)} phút")
        if ss is not None:
            ss_i = int(ss)
            if 0 <= ss_i <= 59 and ss_i != 0:
                parts.append(f"{_int_to_vi(ss_i)} giây")

        if suffix:
            s = suffix.lower().replace(".", "")
            if s == "am":
                parts.append(TIME_SUFFIX_MAP["am"])
            elif s == "pm":
                parts.append(TIME_SUFFIX_MAP["pm_day" if h_i < 18 else "pm_eve"])
            else:  # already a Vietnamese word — preserve verbatim
                parts.append(s)
        return " ".join(parts)

    return TIME_RE.sub(repl, text)


_SWAP_TABLE = str.maketrans({".": ",", ",": "."})


def _looks_us_style(tok: str) -> bool:
    """Heuristic: True if a number token looks like US-style formatting.

    Examples:
      "1,234"       -> True   (comma followed by exactly 3 digits, no dots)
      "1,234.56"    -> True   (comma before dot — US thousands + decimal)
      "1.234"       -> False  (single dot, 3 digits → VN thousands)
      "1.234.567"   -> False  (multiple dots → VN thousands)
      "0,3"         -> False  (comma + 1 digit → VN decimal)
      "25.350"      -> False  (single dot + 3 digits → VN thousands)
    """
    has_comma = "," in tok
    has_dot   = "."   in tok
    if has_comma and has_dot:
        # Whichever appears LAST is the decimal; if comma appears LAST -> VN.
        return tok.rindex(".") > tok.rindex(",")
    if has_comma and not has_dot:
        # Pure comma: US if exactly 3 digits after each comma; VN if 1-2 digits.
        parts = tok.split(",")
        return all(len(p) == 3 for p in parts[1:])
    # Pure dot or pure digits → treat as VN (no swap needed).
    return False


def swap_us_to_vi_numbers(text: str) -> str:
    """Convert US-style number tokens to VN convention so the heavy normalizer
    reads them correctly. Vietnamese-style tokens are left untouched.

    US `1,234.5` -> VN `1.234,5`     (swapped)
    VN `25.350`  -> VN `25.350`      (untouched — already correct)
    VN `0,3`     -> VN `0,3`         (untouched)
    """
    def _maybe_swap(m: 're.Match') -> str:
        tok = m.group(0)
        return tok.translate(_SWAP_TABLE) if _looks_us_style(tok) else tok
    return NUM_TOKEN_RE.sub(_maybe_swap, text)


def apply_symbols(text: str) -> str:
    """Residual sweep over math/currency symbols the heavy normalizer left alone."""
    return SYMBOL_RE.sub(lambda m: SYMBOL_MAP[m.group(0)], text)
