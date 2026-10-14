"""Behavioral regressions for the 0.8.8 detector changes."""

from pathlib import Path

import pytest

from lintlang.detectors.h1 import _detect_skill_metadata
from lintlang.models import AgentConfig, Severity, SkillMeta
from lintlang.patterns import PATTERNS, detect_h6
from lintlang.scanner import scan_file


def _skill(description: str, name: str = "my-skill", directory: str = "my-skill") -> AgentConfig:
    return AgentConfig(
        kind="skill",
        skill=SkillMeta(
            name=name,
            description=description,
            dir_name=directory,
            name_line=2,
            description_line=3,
        ),
    )


@pytest.mark.parametrize(
    ("length", "severity"),
    [
        (1024, None),
        (1025, Severity.LOW),
        (2500, Severity.LOW),
        (2501, Severity.LOW),
        (5000, Severity.LOW),
        (5001, Severity.HIGH),
    ],
)
def test_h17_threshold_boundaries(length: int, severity: Severity | None) -> None:
    description = "Use when " + "x" * (length - len("Use when "))
    findings = [f for f in _detect_skill_metadata(_skill(description)) if f.code == "H1.7"]
    assert [f.severity for f in findings] == ([] if severity is None else [severity])


@pytest.mark.parametrize(
    ("name", "directory", "severity"),
    [
        ("My-Skill", "my-skill", None),
        ("my-skill-v2", "my-skill", None),
        ("my-skill", "my-skill-v2", None),
        ("skill", "my-skill", Severity.MEDIUM),
        ("my", "mystery", Severity.MEDIUM),
        ("my-skill", "other-skill", Severity.MEDIUM),
        ("PDF_Tools", "PDF_Tools", Severity.MEDIUM),
        ("video-toolkit", "video_toolkit", Severity.MEDIUM),
        ("vercel-deploy", "vercel-deploy-claimable", Severity.MEDIUM),
    ],
)
def test_h19_relaxes_only_clear_name_variants(
    name: str, directory: str, severity: Severity | None
) -> None:
    findings = [
        f for f in _detect_skill_metadata(_skill("Use when the user asks for a PDF file.", name, directory))
        if f.code == "H1.9"
    ]
    assert [f.severity for f in findings] == ([] if severity is None else [severity])


def test_h17_retains_1024_boundary_as_host_qualified_low_advice() -> None:
    description = "Use when " + "x" * (1068 - len("Use when "))
    findings = [f for f in _detect_skill_metadata(_skill(description)) if f.code == "H1.7"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.LOW
    assert findings[0].location == "frontmatter.description"
    assert findings[0].description == (
        "Skill 'my-skill' description is 1068 characters; this exceeds the legacy "
        "1024-character guideline. Check the target host limit."
    )


@pytest.mark.parametrize("directory", ["video_toolkit", "vercel-deploy-claimable"])
def test_h19_known_field_mismatches_remain_detected(directory: str) -> None:
    fixture = Path(__file__).resolve().parents[1] / "samples/release_088/skills" / directory / "SKILL.md"
    findings = [f for f in scan_file(fixture, gate=False).structural_findings if f.code == "H1.9"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM


def test_h4_illustrative_path_is_quiet_but_actionable_path_is_reported(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "samples/release_088"
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples/README.md").write_text((fixture / "examples/README.md").read_text())
    source = tmp_path / "AGENTS.md"
    source.write_text((fixture / "AGENTS.md").read_text())
    findings = [f for f in scan_file(source, gate=False).structural_findings if f.code == "H4.5"]
    assert [f.location for f in findings] == ["reference:examples/runner.py"]


def test_h4_nested_template_path_stays_actionable(tmp_path: Path) -> None:
    (tmp_path / "src/templates").mkdir(parents=True)
    source = tmp_path / "AGENTS.md"
    source.write_text("Update `src/templates/release.yaml` before packaging.\n")
    findings = [f for f in scan_file(source, gate=False).structural_findings if f.code == "H4.5"]
    assert [f.location for f in findings] == ["reference:src/templates/release.yaml"]


def test_h6_is_absent_from_active_detectors() -> None:
    assert tuple(PATTERNS) == ("H1", "H2", "H3", "H4", "H7")
    assert detect_h6(AgentConfig(system_prompt="Respond in JSON and Markdown.")) == []


def test_h5_is_removed_from_module_registry_and_scan():
    import lintlang.patterns as patterns
    from lintlang.scanner import scan_source

    assert not hasattr(patterns, "detect_h5")
    assert "H5" not in patterns.PATTERNS
    for prompt in (
        "Be concise. Use your discretion. Continue as needed.",
        "Don't use emojis. Never use bullet lists. Avoid headings. Do not use tables.",
        "You are helpful. " + "Do A. " * 12,
    ):
        result = scan_source(prompt, "prompt.txt", gate=False)
        assert not any(f.pattern_id == "H5" for f in result.structural_findings)
