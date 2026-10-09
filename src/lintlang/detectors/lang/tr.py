"""Turkish use directives and purpose clauses from the labeled corpus.

The generic suffix için occurs in both groups; only the mined building
purpose and explicit skill-use directive become canonical triggers.
"""

import re

_MAP = (
    (r"\bbu skill'i kullanın\b", " use this "),
    (r"\boluşturmak için\b(?!\s+kullanma(?:yın|yınız)?\b)", " use for building "),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), replacement) for pattern, replacement in _MAP)


def normalize(text: str) -> str:
    """Map observed use cues without stemming Turkish words."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text
