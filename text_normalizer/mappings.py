"""Static lookup tables used by the text normalizer.

All maps are simple data — no regex or runtime logic here. Keeping them
isolated lets you tweak them without touching the rule engine.
"""

# Math / currency / punctuation symbols → spoken Vietnamese.
# Applied as a final sweep AFTER the heavy normalizer, so anything it leaves
# untouched still gets a sensible reading.
SYMBOL_MAP = {
    "+": " cộng ",
    "*": " nhân ",
    "/": " trên ",
    "=": " bằng ",
    "%": " phần trăm ",
    "$": " đô la ",
    "€": " euro ",
    "£": " bảng ",
    "₫": " đồng ",
    "&": " và ",
    "@": " a còng ",
    "#": " thăng ",
    "^": " mũ ",
}

# Abbreviation expansions. Order matters — earlier entries win.
# Each entry is (pattern_source, flags, replacement). Compiled in rules.py.
ABBREVIATIONS_SRC = [
    (r"\bTP\.?\s*HCM\b",  True,  "Thành phố Hồ Chí Minh"),
    (r"\bTP\.?\s*HN\b",   True,  "Thành phố Hà Nội"),
    (r"\bQ\.?\s*(\d+)\b", True,  r"Quận \1"),
    (r"\bP\.?\s*(\d+)\b", True,  r"Phường \1"),
    (r"\bsđt\b",          True,  "số điện thoại"),
    (r"\bĐH\b",           False, "Đại học"),
    (r"\bCĐ\b",           False, "Cao đẳng"),
    # Currency codes — expand before the heavy normalizer so the trailing
    # period (e.g. "VND.") doesn't get swallowed by its currency tokenizer.
    (r"\bVND\b",          False, "việt nam đồng"),
    (r"\bUSD\b",          False, "đô la Mỹ"),
    (r"\bEUR\b",          False, "euro"),
    (r"\bGBP\b",          False, "bảng Anh"),
    (r"\bJPY\b",          False, "yên Nhật"),
    (r"\bCNY\b",          False, "nhân dân tệ"),
    (r"\bKRW\b",          False, "won"),
]

# Pronunciation overrides for tokens the model mis-reads. Applied unconditionally
# (i.e. before the "do we need to normalize?" check) so they fire on plain text too.
PRONUNCIATION_OVERRIDES_SRC = [
    # "Pi" / "pi" -> "Pii" forces /pi/ (defeats English /paɪ/ flip).
    (r"\bPi\b", False, "Pii"),
    (r"\bpi\b", False, "pii"),
]

# Spoken Vietnamese for time-suffix tokens. Two-syllable forms picked so the
# model is less likely to drop them.
TIME_SUFFIX_MAP = {
    "am":     "buổi sáng",
    "pm_day": "buổi chiều",   # before 18:00
    "pm_eve": "buổi tối",     # 18:00 and after
}
