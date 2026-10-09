"""Chinese activation cues mined from the labeled FP descriptions.

No translations are invented for unobserved traditional-Chinese spellings.
Bare framework/team applicability and topics explaining when to use tools
also occur in TPs. Only task/intent applicability becomes a selection cue.
Generic 用于/使用 are deliberately left alone.
"""

import re

# (observed phrase pattern, canonical English selection cue).
_MAP = (
    # u-e90388e34391, data-scraper-agent: explicit user intent.
    (r"适用于用户希望", " use when user wants "),
    # u-d7c5c0fc2b53, video-editing: explicit user intent.
    (r"适用于用户想要", " use when user wants "),
    # u-ddd648ea190c, production-scheduling: actionable scheduling purpose.
    (r"适用于调度", " use for scheduling "),
    # u-019875a222a0, quality-nonconformance: actionable investigation purpose.
    (r"适用于调查", " use for investigating "),
    # u-ff75007087c4, customs-trade-compliance; also returns-reverse-logistics.
    (r"适用于处理", " use for handling "),
    (r"当用户", " when user "),
    # u-ae19340ee8cb (TP): 何时使用 introduces a comparison topic, not a
    # condition selecting this skill. FP conditions instead end with 时使用.
    (r"(?<!何)时使用", " when using "),
    (r"(?<!不)触发词：", " trigger: "),
    (r"(?<!不)触发条件：", " trigger: "),
    (r"(?<!不)触发时机：", " trigger: "),
)
_COMPILED = tuple((re.compile(pattern), replacement) for pattern, replacement in _MAP)
_EXCLUSION = re.compile(r"不\s*(?:适用于|触发(?:词|条件|时机)[：:])")


def _negated(text: str, offset: int) -> bool:
    while offset and text[offset - 1].isspace():
        offset -= 1
    if offset and text[offset - 1] == "不":
        return True
    # An exclusion can introduce an entire condition ending with 时使用, or
    # a nested 当用户 cue. Do not let a later phrase bypass that exclusion.
    prefix = re.split(r"[。.!?！？;\n]", text[max(0, offset - 160):offset])[-1]
    return bool(_EXCLUSION.search(prefix))


def normalize(text: str) -> str:
    """Separate canonical cues from Han characters for English word boundaries."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(
            lambda match, source=text, canonical=replacement:
                match.group() if _negated(source, match.start()) else canonical,
            text,
        )
    return text
