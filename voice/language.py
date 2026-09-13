"""
NOVA Voice Assistant - Language Detection
Small helpers that tell NOVA what language the user is speaking so that
the reply and the voice choice follow the user naturally (AUTO mode) or
respect an explicit mode (ENGLISH / HINDI / HINGLISH).

Hinglish detection is heuristic: a Devanagari script wins instantly; otherwise
a small Romanised-Hindi lexicon suggests "hinglish".
"""

import re

DEVANAGARI_RE = re.compile("[\u0900-\u097F]")

# Romanised-Hindi function words common in everyday Speech.
_HIN_ROMAN = {
    "kholo", "khol", "karo", "kari", "karke", "kya", "hai", "hain", "hoon",
    "haan", "nahi", "banao", "bana", "batao", "naam", "mera", "meri", "mujhe",
    "tumhara", "tumhari", "aap", "kaise", "kitne", "kahan", "kab", "kaun",
    "theek", "sahi", "band", "chalu", "rakho", "rakh", "dikhao", "dekh", "lo",
    "do", "jao", "aao", "pe", "par", "mein", "main", "aur", "pakka", "zaroor",
    "sab", "thoda", "zyada", "kam", "badh", "ghat", "baki", "kal",
}

_LANG_MODES = ("AUTO", "ENGLISH", "HINDI", "HINGLISH")


def has_devanagari(text: str) -> bool:
    return bool(text) and bool(DEVANAGARI_RE.search(text))


def detect_lang(text: str) -> str:
    """Return 'hi' | 'hinglish' | 'en' for a piece of user text."""
    if not text:
        return "en"
    if has_devanagari(text):
        return "hi"
    words = set(re.findall(r"[a-z']+", text.lower()))
    hits = words & _HIN_ROMAN
    if hits:
        return "hinglish"
    return "en"


def effective_language(user_lang: str, mode: str = "AUTO",
                       auto_detect: bool = True) -> str:
    """
    Combine the detected user language with the configured language mode.
    Returns the language NOVA should respond and speak in.
    """
    mode = (mode or "AUTO").upper()
    if mode == "ENGLISH":
        return "en"
    if mode == "HINDI":
        return "hi"
    if mode == "HINGLISH":
        return "hinglish"
    # AUTO
    if not auto_detect:
        return user_lang if user_lang in ("hi", "hinglish", "en") else "en"
    return user_lang or "en"


def script_label(lang: str) -> str:
    return {"hi": "HINDI", "hinglish": "HINGLISH",
            "en": "ENGLISH"}.get(lang, lang.upper())