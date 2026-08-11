"""Quoted examples stay inert while equivalent live instructions still fire."""

from __future__ import annotations

from lintlang.patterns import AgentConfig, detect_h2, detect_h5

# The exact shape that blocked the 0.4.0 commit, reduced to its essentials.
DOCUMENTATION_DESCRIBING_ANTIPATTERNS = (
    "## H2: Missing Constraint Scaffolding\n"
    'Catches: unbounded retry loops ("keep trying until"), negative\n'
    'termination ("don\'t stop until"), "continue until" without limits.\n'
    "\n"
    "## H5: Implicit Instruction Failure\n"
    'Catches: vague qualifiers ("be concise", "be helpful"), ambiguous\n'
    'conditionals ("as needed", "when appropriate").\n'
)


def test_quoted_antipatterns_do_not_fire() -> None:
    """Quoted examples are documentation, not live instructions."""
    config = AgentConfig(system_prompt=DOCUMENTATION_DESCRIBING_ANTIPATTERNS)
    findings = detect_h2(config) + detect_h5(config)

    assert findings == []


def test_the_same_text_as_a_real_instruction_must_always_fire() -> None:
    """The guard rail on any future fix.

    A scope classifier must not silence genuine unbounded instructions. This
    text carries the same phrase as a directive rather than as a quoted example,
    and must keep firing no matter how quotation handling changes.
    """
    config = AgentConfig(
        system_prompt=(
            "You are a support agent.\n"
            "Keep trying until the ticket is resolved.\n"
            "Do not stop until the customer confirms.\n"
        )
    )
    assert detect_h2(config), "a live unbounded instruction must always be reported"
