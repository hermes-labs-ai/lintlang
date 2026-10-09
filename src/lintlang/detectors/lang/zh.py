"""Chinese selection cues observed only in the 172-FP cohort.

No translations are invented for unobserved traditional-Chinese spellings.
Generic 用于/使用 also occur in TPs and are deliberately left alone.
"""

import re

# (observed phrase pattern, canonical English selection cue).
_MAP = (
    (r"当用户", " when user "),
    (r"适用于", " use for "),
    (r"时使用", " when using "),
    (r"(?<!不)触发词：", " trigger: "),
    (r"(?<!不)触发条件：", " trigger: "),
    (r"(?<!不)触发时机：", " trigger: "),
)
_COMPILED = tuple((re.compile(pattern), replacement) for pattern, replacement in _MAP)


def _negated(text: str, offset: int) -> bool:
    while offset and text[offset - 1].isspace():
        offset -= 1
    return bool(offset and text[offset - 1] == "不")


def normalize(text: str) -> str:
    """Separate canonical cues from Han characters for English word boundaries."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(
            lambda match, source=text, canonical=replacement:
                match.group() if _negated(source, match.start()) else canonical,
            text,
        )
    return text
