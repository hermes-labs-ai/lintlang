"""Release regressions for the learned gate's delivered behavior."""

import json
from pathlib import Path

import pytest

from lintlang.cli import main
from lintlang.gate import FPGate
from lintlang.gate.features import extract_features, get_feature_names
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "bad_tool_descriptions.yaml"


def test_gate_features_use_explicit_path_and_source_context():
    finding = {
        "rule": "H1.8", "severity": "medium", "pattern_name": "Skill",
        "evidence": "Use when needed", "context": "---\n# When to use\n",
        "file_path": "skills/demo/SKILL.md", "id": "other-test-fallback",
    }
    features = extract_features(finding)
    assert features["basename_SKILL.md"] == 1
    assert features["agent_dir"] == 1
    assert features["test_path"] == 0
    assert features["yaml_frontmatter"] == 1
    assert features["when_to_use_section"] == 1
    assert extract_features({**finding, "file_path": r"skills\demo\SKILL.md"})["basename_SKILL.md"] == 1


def test_artifact_decisions_are_finite_and_model_is_measurable():
    gate = FPGate()
    assert gate.feature_names == get_feature_names()
    decision, probability = gate.classify({
        "rule": "H1.8", "severity": "medium", "pattern_name": "Skill",
        "evidence": "Use when refactoring Python code", "context": "# When to use",
        "file_path": "skills/demo/SKILL.md",
    })
    assert decision in {"KEEP", "ESCALATE", "DISMISS"}
    assert 0 <= probability <= 1


def test_invalid_artifact_fails_open_with_diagnostic(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    original = FPGate().thresholds
    (artifact_dir / "thresholds.json").write_text(json.dumps(original))
    from lintlang.gate import gate as gate_module

    monkeypatch.setattr(gate_module, "DEFAULT_ARTIFACTS_DIR", artifact_dir)
    raw = scan_file(SAMPLE, gate=False)
    gated = scan_file(SAMPLE, gate=True)
    assert gated.gate_status == "unavailable"
    assert "Gate unavailable" in gated.gate_error
    assert compute_verdict(gated) == "ERROR"
    assert [(f.code, f.location) for f in gated.structural_findings] == [
        (f.code, f.location) for f in raw.structural_findings
    ]
    assert all(f.gate_decision is None for f in gated.structural_findings)


def test_gate_dismisses_visible_findings_and_receives_real_context(monkeypatch):
    seen = []

    def classify(self, finding):
        seen.append(finding)
        return "DISMISS", 0.01

    monkeypatch.setattr(FPGate, "classify", classify)
    raw = scan_file(SAMPLE, gate=False)
    gated = scan_file(SAMPLE, gate=True)
    assert seen
    assert gated.structural_findings == []
    assert gated.raw_findings_count == len(raw.structural_findings)
    assert gated.suppressed_count == len(raw.structural_findings)
    assert compute_verdict(gated) == "PASS"
    assert all(item["rule"].count("H1.H1") == 0 for item in seen)
    assert all(item["file_path"] == str(SAMPLE) for item in seen)
    assert all(item["context"] == SAMPLE.read_text() for item in seen)


def test_invalid_later_gate_decision_leaves_batch_unannotated(monkeypatch):
    calls = 0

    def classify(self, finding):
        nonlocal calls
        calls += 1
        return ("INVALID", 0.5) if calls == 2 else ("KEEP", 0.9)

    monkeypatch.setattr(FPGate, "classify", classify)
    raw = scan_file(SAMPLE, gate=False)
    gated = scan_file(SAMPLE, gate=True)
    assert calls == len(raw.structural_findings) > 2
    assert gated.gate_status == "unavailable"
    assert gated.gate_error == "Gate unavailable (ValueError); detector findings retained"
    assert [finding.code for finding in gated.structural_findings] == [
        finding.code for finding in raw.structural_findings
    ]
    assert all(finding.gate_decision is None and finding.gate_probability is None for finding in gated.structural_findings)


@pytest.mark.parametrize("output_format", ["json", "sarif", "gitlab"])
def test_gate_decisions_reach_machine_outputs(output_format, capsys, monkeypatch):
    monkeypatch.chdir(SAMPLE.parents[1])
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: ("DISMISS", 0.01))
    rc = main(["scan", str(SAMPLE), "--gate", "--format", output_format])
    output = capsys.readouterr().out
    assert rc == 0
    document = json.loads(output)
    if output_format == "json":
        assert document[0]["gate"]["status"] == "evaluated"
        assert document[0]["structural_findings"] == []
        assert document[0]["gate"]["suppressed"] == document[0]["gate"]["raw_findings"] > 0
    elif output_format == "sarif":
        results = document["runs"][0]["results"]
        assert results == []
        gate = document["runs"][0]["properties"]["lintlangGate"]
        assert gate["suppressed"] == gate["rawFindings"] > 0
    else:
        assert document == []
