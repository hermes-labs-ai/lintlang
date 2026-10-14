"""The Muse candidate's 13 original regressions, adapted to canonical LintLang.

The case names and group counts track muse/release/0.8.8:tests/test_090_changes.py.
Additional boundary and actionable-reference coverage lives in
test_release_088_detectors.py.
"""

import time

from lintlang.detectors.h1 import _detect_skill_metadata
from lintlang.gate import FPGate
from lintlang.models import AgentConfig, Severity, SkillMeta
from lintlang.patterns import _NON_ACTIONABLE_PATH_SEGMENTS, PATTERNS
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file


def _skill_config(description: str, *, name: str = "test-skill", directory: str = "test-skill") -> AgentConfig:
    return AgentConfig(
        kind="skill",
        skill=SkillMeta(
            name=name,
            description=description,
            has_name=True,
            has_description=True,
            name_line=1,
            description_line=2,
            dir_name=directory,
        ),
    )


def _findings(config: AgentConfig, code: str):
    return [finding for finding in _detect_skill_metadata(config) if finding.code == code]


class TestH6Removal:
    def test_h6_not_in_patterns(self):
        assert "H6" not in PATTERNS

    def test_remaining_patterns(self):
        assert set(PATTERNS) == {"H1", "H2", "H3", "H4", "H7"}


class TestH17TieredLimits:
    def test_under_2500_no_high_finding(self):
        # Muse expected no finding here. The labeled corpus has a verified TP
        # above 1024, so 0.8.8 keeps a LOW diagnostic while avoiding a block.
        findings = _findings(_skill_config("x" * 2400), "H1.7")
        assert len(findings) == 1
        assert findings[0].severity is Severity.LOW

    def test_over_2500_advisory(self):
        findings = _findings(_skill_config("x" * 3000), "H1.7")
        assert len(findings) == 1
        assert findings[0].severity is Severity.LOW

    def test_over_5000_flag(self):
        findings = _findings(_skill_config("x" * 6000), "H1.7")
        assert len(findings) == 1
        assert findings[0].severity is Severity.HIGH


class TestH4PathExclusions:
    def test_exclusion_prefixes_defined(self):
        assert {"examples", "templates", "prompts", "fixtures"} <= _NON_ACTIONABLE_PATH_SEGMENTS

    def test_example_path_excluded(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        (skill_dir / "examples").mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "# Skill\nSee [example](examples/demo.json) for usage.\n"
            "Run `examples/check.py` before release.\n"
        )
        findings = [finding for finding in scan_file(skill_file, gate=False).structural_findings if finding.code == "H4.5"]
        assert [finding.location for finding in findings] == ["reference:examples/check.py"]


class TestH19RelaxedValidation:
    def test_title_case_name_is_info(self):
        assert _findings(
            _skill_config("Use when the user asks for a PDF file.", name="My-Skill", directory="my-skill"),
            "H1.9",
        ) == []

    def test_substring_match_accepted(self):
        assert _findings(
            _skill_config("Use when the user asks for a PDF file.", name="my-skill-v2", directory="my-skill"),
            "H1.9",
        ) == []

    def test_exact_match_no_finding(self):
        assert _findings(_skill_config("Use when the user asks for a PDF file."), "H1.9") == []


class TestGateIntegration:
    def test_gate_loads(self):
        gate = FPGate()
        assert gate.feature_names
        assert {"keep", "dismiss"} <= gate.thresholds.keys()

    def test_gate_classifies(self):
        decision, probability = FPGate().classify({
            "rule": "H1.8",
            "severity": "medium",
            "pattern_name": "Tool Description Ambiguity",
            "evidence": "Use when refactoring Python code",
            "context": "# Skill\n## When to use",
        })
        assert decision in {"KEEP", "ESCALATE", "DISMISS"}
        assert 0 <= probability <= 1

    def test_gate_latency_under_100ms(self):
        gate = FPGate()
        finding = {"rule": "H1.8", "severity": "medium", "pattern_name": "Test", "evidence": "", "context": ""}
        start = time.perf_counter_ns()
        for _ in range(100):
            gate.classify(finding)
        average_ms = (time.perf_counter_ns() - start) / 100 / 1e6
        assert average_ms < 100


def test_gate_unavailability_is_explicit_even_when_there_are_no_findings(tmp_path, monkeypatch):
    source = tmp_path / "empty.txt"
    source.write_text("")

    def fail_if_loaded(self, *args, **kwargs):
        raise AssertionError("gate model should not load without findings")

    monkeypatch.setattr(FPGate, "__init__", fail_if_loaded)
    result = scan_file(source, gate=True)
    assert result.structural_findings == []
    assert result.gate_status == "unavailable"
    assert compute_verdict(result) == "ERROR"
    assert result.gate_error is not None
