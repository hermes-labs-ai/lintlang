"""H2/H4 scope-classifier integration regressions."""

from __future__ import annotations

import pytest

from lintlang.patterns import AgentConfig, detect_h2, detect_h4


@pytest.mark.parametrize(
    ("detector", "trigger"),
    [
        (detect_h2, "keep trying until the request succeeds"),
        (detect_h4, "remember everything the user says"),
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
    ],
)
def test_live_instruction_still_fires(detector, prompt: str) -> None:
    assert detector(AgentConfig(system_prompt=prompt))


@pytest.mark.parametrize(
    "quoted_marker",
    [
        'Documentation example: "session".',
        "Documentation code: `task boundary`.",
    ],
)
def test_quoted_or_code_boundary_markers_do_not_satisfy_long_prompt_boundary(
    quoted_marker: str,
) -> None:
    # H4's length rule now requires demonstrated cross-context statefulness, so the
    # prompt carries a live one. The point under test is unchanged: the only
    # boundary vocabulary present is quoted or in code, and must not exempt it.
    prompt = (
        ("Operational guidance. " * 30)
        + "Use the conversation history when you answer. "
        + quoted_marker
    )

    findings = detect_h4(AgentConfig(system_prompt=prompt))

    assert any("no context boundary" in finding.description.lower() for finding in findings)


@pytest.mark.parametrize(
    ("detector", "prompt"),
    [
        (detect_h2, 'Example with an unclosed quote: "keep trying until the request succeeds.'),
        (detect_h4, 'Example with an unclosed quote: "remember everything the user says.'),
    ],
)
def test_unavailable_scope_preserves_existing_findings(detector, prompt: str) -> None:
    assert detector(AgentConfig(system_prompt=prompt))
