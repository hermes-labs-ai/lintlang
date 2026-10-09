"""Japanese activation clauses mined from the frozen FP descriptions.

使用した/使用して describe implementation methods in both label groups;
they are not activation clauses and are never normalized by themselves.
"""

import re

_MAP = (
    (r"場合にこのスキルを使用(?!しない|しません|するな|すべきではない)", " use this when "),
    (r"場合に使用(?!しない|しません|するな|すべきではない)", " use when "),
    (r"ときに使用(?!しない|しません|するな|すべきではない)", " use when "),
    (r"際に使用(?!しない|しません|するな|すべきではない)", " use when "),
    (r"時に使用(?!しない|しません|するな|すべきではない)", " use when "),
    (r"ために使用(?!しない|しません|するな|すべきではない)", " used for "),
    (r"リクエストに使用(?!しない|しません|するな|すべきではない)", " use for requests "),
    (r"このスキルを使用してください", " use this "),
    (r"トリガー[：:]", " trigger: "),
    (r"トリガーされます", " triggered "),
    (r"ときにアクティベーション", " trigger when "),
    (r"開始時に", " when starting "),
)
_COMPILED = tuple((re.compile(pattern), replacement) for pattern, replacement in _MAP)


def normalize(text: str) -> str:
    """Map observed activation clauses, retaining all other text."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text
