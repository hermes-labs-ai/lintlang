"""Delivered gate policy and legacy raw-mode boundaries."""

import json
from pathlib import Path

import pytest

from lintlang.cli import _gate_threshold, main
from lintlang.gate import FPGate
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file, scan_python_source, scan_source

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "bad_tool_descriptions.yaml"


@pytest.mark.parametrize(
    ("decision", "score", "verdict", "exit_code"),
    [("KEEP", 0.9, "FAIL", 1), ("ESCALATE", 0.5, "REVIEW", 0), ("DISMISS", 0.1, "PASS", 0)],
)
def test_default_gate_policy_api_and_cli(decision, score, verdict, exit_code, monkeypatch, capsys):
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: (decision, score))
    raw = scan_file(SAMPLE, gate=False)
    result = scan_file(SAMPLE)
    assert compute_verdict(result) == verdict
    assert result.raw_findings_count == len(raw.structural_findings) > 0
    assert result.suppressed_count == (len(raw.structural_findings) if decision == "DISMISS" else 0)
    assert len(result.structural_findings) == result.raw_findings_count - result.suppressed_count
    assert main(["scan", str(SAMPLE), "--format", "json", "--fail-on", "review"]) == exit_code
    payload = json.loads(capsys.readouterr().out)[0]
    assert payload["verdict"] == verdict
    assert payload["gate"]["raw_findings"] == result.raw_findings_count
    assert payload["gate"]["suppressed"] == result.suppressed_count
    assert payload["gate"]["thresholds"] == {"keep": 0.85, "dismiss": 0.15}
    assert main(["scan", str(SAMPLE), "--format", "sarif"]) == exit_code
    sarif = json.loads(capsys.readouterr().out)["runs"][0]["results"]
    assert len(sarif) == len(result.structural_findings)
    for finding in sarif:
        assert finding["properties"]["lintlangGateAdvisory"] is (decision != "KEEP")


def test_no_gate_preserves_raw_severity_and_fail_on(monkeypatch, capsys):
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: ("DISMISS", 0.1))
    raw = scan_file(SAMPLE, gate=False)
    assert compute_verdict(raw) == "FAIL"
    assert len(raw.structural_findings) > 0
    assert main(["scan", str(SAMPLE), "--no-gate", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)[0]
    assert "gate" not in payload
    assert len(payload["structural_findings"]) == len(raw.structural_findings)
    assert main(["scan", str(SAMPLE), "--no-gate", "--fail-on", "fail", "--format", "json"]) == 1


def test_threshold_bounds_and_single_keep_override(monkeypatch, capsys):
    assert _gate_threshold("0.7") == (0.7, 0.15)
    assert _gate_threshold("0.9,0.2") == (0.9, 0.2)
    for value in ("nan", "inf", "0.1", "0.5,0.5", "0.5,-0.1", "1.1,0.1", "abc", "0.8,0.2,0.1"):
        with pytest.raises(Exception, match="finite 0 <= DISMISS < KEEP <= 1"):
            _gate_threshold(value)
    monkeypatch.setattr(FPGate, "_predict_proba", lambda self, features: 0.8)
    default = scan_file(SAMPLE)
    lowered = scan_file(SAMPLE, gate_thresholds=(0.7, 0.15))
    assert all(f.gate_decision == "ESCALATE" for f in default.structural_findings)
    assert all(f.gate_decision == "KEEP" for f in lowered.structural_findings)
    assert compute_verdict(default) == "REVIEW"
    assert compute_verdict(lowered) == "FAIL"
    assert main(["scan", str(SAMPLE), "--gate-threshold", "0.7", "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)[0]
    assert payload["gate"]["thresholds"] == {"keep": 0.7, "dismiss": 0.15}


def test_no_gate_rejects_gate_threshold(capsys):
    assert main(["scan", str(SAMPLE), "--no-gate", "--gate-threshold", "0.8"]) == 2
    assert "requires the gate" in capsys.readouterr().err


def test_explicit_min_severity_selects_which_keep_findings_block(tmp_path, monkeypatch, capsys):
    source = tmp_path / "priority.yaml"
    source.write_text("system_prompt: Use the conversation history when you answer. " + "Operational guidance. " * 30)
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: ("KEEP", 0.9))
    assert main(["scan", str(source), "--format", "json"]) == 1
    unfiltered = json.loads(capsys.readouterr().out)[0]
    assert unfiltered["verdict"] == "FAIL"
    assert [finding["code"] for finding in unfiltered["structural_findings"]] == ["H4"]
    assert main(["scan", str(source), "--min-severity", "high", "--format", "json"]) == 0
    filtered = json.loads(capsys.readouterr().out)[0]
    assert filtered["verdict"] == "PASS"
    assert filtered["structural_findings"] == []
    assert filtered["gate"]["raw_findings"] == 1
    assert filtered["gate"]["suppressed"] == 0


def test_explicit_fail_under_can_block_all_escalate_scan(monkeypatch, capsys):
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: ("ESCALATE", 0.5))
    assert main(["scan", str(SAMPLE), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["verdict"] == "REVIEW"
    assert main(["scan", str(SAMPLE), "--fail-under", "100", "--format", "json"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)[0]["verdict"] == "REVIEW"
    assert "Quality score" in output.err


def test_unavailable_model_is_error_even_with_no_raw_findings(monkeypatch):
    from lintlang.gate import gate as gate_module

    monkeypatch.setattr(gate_module, "DEFAULT_ARTIFACTS_DIR", Path("/definitely/no/model"))
    result = scan_source("system_prompt: You are helpful.", "agent.yaml")
    assert result.raw_findings_count == 0
    assert result.gate_status == "unavailable"
    assert compute_verdict(result) == "ERROR"


def test_python_gate_receives_full_source_context(monkeypatch):
    source = "CONFIDENCE_THRESHOLD = 0.75\nX = 'context marker'\n"
    seen = []

    def classify(self, finding):
        seen.append(finding)
        return "KEEP", 0.9

    monkeypatch.setattr(FPGate, "classify", classify)
    result = scan_python_source(source, "pipeline.py")
    assert result.raw_findings_count > 0
    assert seen and all(item["context"] == source and item["file_path"] == "pipeline.py" for item in seen)


def test_unavailable_model_is_visible_in_machine_outputs(monkeypatch, capsys):
    from lintlang.gate import gate as gate_module

    monkeypatch.chdir(SAMPLE.parents[1])
    monkeypatch.setattr(gate_module, "DEFAULT_ARTIFACTS_DIR", Path("/definitely/no/model"))
    assert main(["scan", str(SAMPLE), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)[0]
    assert payload["verdict"] == "ERROR"
    assert payload["gate"]["status"] == "unavailable"
    assert payload["structural_findings"]  # Raw evidence retained for diagnosis.
    assert main(["scan", str(SAMPLE), "--format", "sarif"]) == 1
    run = json.loads(capsys.readouterr().out)["runs"][0]
    assert run["invocations"][0]["executionSuccessful"] is False
    notifications = run["invocations"][0]["toolExecutionNotifications"]
    assert any(item["descriptor"]["id"] == "LL_GATE_UNAVAILABLE" for item in notifications)


def test_gate_keeps_only_visible_findings_in_sarif_and_gitlab(monkeypatch, capsys):
    monkeypatch.chdir(SAMPLE.parents[1])
    decisions = iter(["KEEP", "ESCALATE", "DISMISS"] * 50)
    monkeypatch.setattr(FPGate, "classify", lambda self, finding: (next(decisions), 0.5))
    result = scan_file(SAMPLE)
    assert result.suppressed_count > 0
    assert {f.gate_decision for f in result.structural_findings} == {"KEEP", "ESCALATE"}
    decisions = iter(["KEEP", "ESCALATE", "DISMISS"] * 50)
    assert main(["scan", str(SAMPLE), "--format", "sarif"]) == 1
    sarif = json.loads(capsys.readouterr().out)["runs"][0]
    assert len(sarif["results"]) == len(result.structural_findings)
    assert sarif["properties"]["lintlangGate"]["suppressed"] == result.suppressed_count
    assert {item["properties"]["lintlangGateDecision"] for item in sarif["results"]} == {"KEEP", "ESCALATE"}
    assert {(item["properties"]["lintlangGateDecision"], item["level"]) for item in sarif["results"]} == {
        ("KEEP", "error"), ("ESCALATE", "warning"),
    }
    decisions = iter(["KEEP", "ESCALATE", "DISMISS"] * 50)
    main(["scan", str(SAMPLE), "--format", "gitlab"])
    output = capsys.readouterr()
    gitlab = json.loads(output.out)
    assert gitlab
    assert all("DISMISS" not in item["description"] for item in gitlab)
    assert {item["severity"] for item in gitlab} == {"blocker", "major"}
    assert "dismissed from GitLab output" in output.err
