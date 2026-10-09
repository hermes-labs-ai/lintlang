"""Offline H1.8 trigger adapters, mined from the frozen labeled descriptions.

Script routing is deliberately heuristic. Unsupported languages pass through;
these modules normalize selection cues, not entire descriptions or labels.
"""

from __future__ import annotations

import re

from . import en, ja, tr, zh

_KANA = re.compile(r"[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fd-\u30ff\uff66-\uff9f]")
_HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\uac00-\ud7a3\ud7b0-\ud7ff]")
_HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002ebef]")
# The ASCII cues include the corpus's Turkish Python description, which has
# no Turkish-specific characters. Folder locale is never consulted.
_TURKISH = re.compile(r"[çğıöşüÇĞİÖŞÜ]|(?i:\b(?:kullanarak|kullanın|metodolojisi|gereksinimleri)\b)")
_SPANISH = re.compile(r"[ñáéíóú¿¡]|\b(?:para|patrones|desarrollo|pruebas|habilidad)\b", re.IGNORECASE)
_NORMALIZERS = {"en": en.normalize, "ja": ja.normalize, "tr": tr.normalize, "zh": zh.normalize}


def detect(text: str) -> str:
    """Route by script, then corpus-observed Turkish/Spanish spelling cues.

    Kana precedes Han because Japanese commonly contains both. Hangul precedes
    Han for Korean containing Hanja. Latin text without a known cue uses en;
    this is a best-effort router, not a general language classifier.
    """
    if _KANA.search(text):
        return "ja"
    if _HANGUL.search(text):
        return "ko"
    if _HAN.search(text):
        return "zh"
    if _TURKISH.search(text):
        return "tr"
    if _SPANISH.search(text):
        return "es"
    return "en"


def normalize(text: str, language: str = "auto") -> str:
    """Return text for the unchanged English trigger gate; keep input evidence."""
    if language == "auto":
        language = detect(text)
    normalizer = _NORMALIZERS.get(language)
    if normalizer is None:
        return text
    # Supported descriptions can code-switch: a Han/kana parenthetical must
    # not hide a mined English cue elsewhere in the same description.
    return normalizer(en.normalize(text) if language != "en" else text)
