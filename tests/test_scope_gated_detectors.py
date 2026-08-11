"""H2/H4/H5 scope-classifier integration regressions."""

from __future__ import annotations

import pytest

from lintlang.patterns import AgentConfig, detect_h2, detect_h4, detect_h5


@pytest.mark.parametrize(
    ("detector", "trigger"),
    [
        (detect_h2, "keep trying until the request succeeds"),
        (detect_h4, "remember everything the user says"),
        (detect_h5, "be concise"),
    ],
)
@pytest.mark.parametrize(
    "template",
    [
        'Documentation example: "{trigger}".',
        "Documentation code: `{trigger}`.",
    ],
)
def test_quoted_or_code_examples_do_not_fire(detector, trigger: str, template: str) -> None:
    config = AgentConfig(system_prompt=template.format(trigger=trigger))

    assert detector(config) == []


@pytest.mark.parametrize(
    ("detector", "prompt"),
    [
        (detect_h2, "Keep trying until the request succeeds."),
        (detect_h4, "Remember everything the user says."),
        (detect_h5, "Be concise."),
    ],
)
def test_live_instruction_still_fires(detector, prompt: str) -> None:
    assert detector(AgentConfig(system_prompt=prompt))


def test_live_h5_negative_instruction_still_fires() -> None:
    """NEGATED scope is operative for H5's own negative-instruction rule."""
    findings = detect_h5(AgentConfig(system_prompt="Don't use emojis."))

    assert any("negative instruction" in finding.description.lower() for finding in findings)


def test_quoted_h5_negative_instruction_does_not_fire() -> None:
    findings = detect_h5(AgentConfig(system_prompt='Documentation example: "Don\'t use emojis."'))

    assert findings == []


@pytest.mark.parametrize(
    ("detector", "prompt"),
    [
        (detect_h2, 'Example with an unclosed quote: "keep trying until the request succeeds.'),
        (detect_h4, 'Example with an unclosed quote: "remember everything the user says.'),
        (detect_h5, 'Example with an unclosed quote: "be concise.'),
    ],
)
def test_unavailable_scope_preserves_existing_findings(detector, prompt: str) -> None:
    assert detector(AgentConfig(system_prompt=prompt))
