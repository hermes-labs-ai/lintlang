"""GitLab Code Quality report and CLI contracts."""

import json

import pytest

from lintlang.cli import main
from lintlang.gitlab import format_gitlab
from lintlang.models import Finding, Severity, SourceRegion
from lintlang.scanner import input_error_result


def _finding(severity=Severity.HIGH, *, line=3, location="system_prompt", description="Unbounded retry"):
    return Finding(
        pattern_id="H2", pattern_name="Missing constraints", severity=severity,
        location=location, description=description, suggestion="Add a retry limit.",
        evidence="PRIVATE SOURCE TEXT", source_region=SourceRegion(line, line) if line else None,
    )


def _result(path, *findings):
    result = input_error_result(path, "fixture")
    result.input_error = None
    result.structural_findings = list(findings)
    return result


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (Severity.CRITICAL, "blocker"), (Severity.HIGH, "critical"),
        (Severity.MEDIUM, "major"), (Severity.LOW, "minor"), (Severity.INFO, "info"),
    ],
)
def test_required_fields_and_severity_map(tmp_path, severity, expected):
    source = tmp_path / "configs" / "agent instructions.md"
    rendered, omitted = format_gitlab(
        {str(source): _result(source, _finding(severity))}, repository_root=tmp_path,
    )
    [item] = json.loads(rendered)
    assert omitted == 0
    assert set(item) == {"description", "check_name", "fingerprint", "severity", "location"}
    assert item["severity"] == expected
    assert item["check_name"] == "H2"
    assert item["location"] == {"path": "configs/agent instructions.md", "lines": {"begin": 3}}
    assert len(item["fingerprint"]) == 64
    assert "PRIVATE SOURCE TEXT" not in rendered


def test_fingerprints_survive_line_shifts_and_distinguish_repeated_findings(tmp_path):
    source = tmp_path / "agent.md"
    first = _result(source, _finding(line=3), _finding(line=8))
    moved = _result(source, _finding(line=13), _finding(line=18))
    first_items = json.loads(format_gitlab({str(source): first}, repository_root=tmp_path)[0])
    moved_items = json.loads(format_gitlab({str(source): moved}, repository_root=tmp_path)[0])
    assert len({item["fingerprint"] for item in first_items}) == 2
    assert [item["fingerprint"] for item in first_items] == [
        item["fingerprint"] for item in moved_items
    ]


def test_python_fingerprint_does_not_depend_on_absolute_path_or_line(tmp_path):
    source = tmp_path / "pipeline.py"
    old = _finding(line=4, location=f"{source}:4")
    moved = _finding(line=14, location=f"{source}:14")
    old_item = json.loads(format_gitlab({str(source): _result(source, old)}, repository_root=tmp_path)[0])[0]
    new_item = json.loads(format_gitlab({str(source): _result(source, moved)}, repository_root=tmp_path)[0])[0]
    assert old_item["fingerprint"] == new_item["fingerprint"]


def test_order_is_independent_of_input_order_and_unlocated_findings_are_omitted(tmp_path):
    a = tmp_path / "a.md"
    z = tmp_path / "z.md"
    results = {
        str(z): _result(z, _finding(line=None), _finding(line=5)),
        str(a): _result(a, _finding(line=2)),
    }
    forward, omitted = format_gitlab(results, repository_root=tmp_path)
    reversed_output, reversed_omitted = format_gitlab(
        dict(reversed(list(results.items()))), repository_root=tmp_path,
    )
    assert (forward, omitted) == (reversed_output, reversed_omitted)
    assert omitted == 1
    assert [item["location"]["path"] for item in json.loads(forward)] == ["a.md", "z.md"]


def test_same_file_requested_twice_does_not_duplicate_gitlab_finding(tmp_path):
    source = tmp_path / "agent.md"
    results = {
        "agent.md": _result(source, _finding()),
        str(source): _result(source, _finding()),
    }
    report, omitted = format_gitlab(results, repository_root=tmp_path)
    assert omitted == 0
    assert len(json.loads(report)) == 1


def test_cli_multifile_report_keeps_json_clean_and_input_error_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    source = tmp_path / "pipeline.py"
    source.write_text("CONFIDENCE_THRESHOLD = 0.75\n")
    status = main(["scan", "--no-gate", "pipeline.py", "missing.yaml", "--format", "gitlab"])
    captured = capsys.readouterr()
    assert status == 1
    report = json.loads(captured.out)
    assert report
    assert all(item["location"]["path"] == "pipeline.py" for item in report)
    assert all(type(item["location"]["lines"]["begin"]) is int for item in report)
    assert "Input error" in captured.err
    assert "Error:" not in captured.out


def test_cli_unlocated_finding_still_trips_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    source = tmp_path / "agent.yaml"
    source.write_text("system_prompt: Keep trying until it works.\n")
    monkeypatch.setattr(
        "lintlang.cli.scan_file",
        lambda path, **kwargs: _result(path, _finding(line=None)),
    )
    assert main(["scan", "--no-gate", "agent.yaml", "--format", "gitlab"]) == 1
    advisory = capsys.readouterr()
    assert json.loads(advisory.out) == []
    assert "omitted" in advisory.err
    status = main(["scan", "--no-gate", "agent.yaml", "--format", "gitlab", "--fail-on", "review"])
    captured = capsys.readouterr()
    assert status == 1
    assert json.loads(captured.out) == []
    assert "omitted" in captured.err
    assert "Verdict:" in captured.err


def test_cli_empty_and_baseline_errors_return_array(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / "empty").mkdir()
    assert main(["scan", "--no-gate", "empty", "--format", "gitlab"]) == 1
    assert json.loads(capsys.readouterr().out) == []
    assert main(["scan", "--no-gate", "empty", "--format", "gitlab", "--allow-empty"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    source = tmp_path / "agent.md"
    source.write_text("Keep trying until it works.\n")
    assert main(["scan", "--no-gate", "agent.md", "--format", "gitlab", "--baseline", "missing.json"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert "Baseline:" in captured.err


def test_cli_baseline_suppresses_reported_findings(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    source = tmp_path / "pipeline.py"
    source.write_text("CONFIDENCE_THRESHOLD = 0.75\n")
    assert main(["scan", "--no-gate", "pipeline.py", "--format", "gitlab", "--write-baseline", "base.json"]) == 0
    assert json.loads(capsys.readouterr().out)
    assert main(["scan", "--no-gate", "pipeline.py", "--format", "gitlab", "--baseline", "base.json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_cli_subdirectory_invocation_uses_repository_relative_path(tmp_path, monkeypatch, capsys):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "configs"
    nested.mkdir()
    (nested / "pipeline.py").write_text("CONFIDENCE_THRESHOLD = 0.75\n")
    monkeypatch.chdir(nested)
    assert main(["scan", "--no-gate", "pipeline.py", "--format", "gitlab"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report
    assert all(item["location"]["path"] == "configs/pipeline.py" for item in report)


def test_cli_rejects_outside_repo_path_without_leaking_absolute_path(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    source = tmp_path / "outside.py"
    source.write_text("CONFIDENCE_THRESHOLD = 0.75\n")
    monkeypatch.chdir(root)
    assert main(["scan", "--no-gate", str(source), "--format", "gitlab"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert "output error" in captured.err
    assert str(source) not in captured.out
