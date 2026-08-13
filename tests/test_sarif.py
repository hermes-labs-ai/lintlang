"""Contract tests for deterministic SARIF 2.1.0 output."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft4Validator

from lintlang.patterns import Finding, Severity, SourceRegion
from lintlang.sarif import (
    SARIF_SCHEMA_URI,
    format_sarif,
    prepare_sarif_results,
    repository_artifact_uri,
)
from lintlang.scanner import ScanResult, input_error_result, scan_file

SCHEMA_PATH = Path(__file__).parent / "schemas" / "sarif-schema-2.1.0.json"
OASIS_SCHEMA_SHA256 = "c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e"


def _result(
    path: str | Path,
    *findings: Finding,
    input_error: str | None = None,
) -> ScanResult:
    result = input_error_result(path, input_error or "test fixture")
    result.input_error = input_error
    result.structural_findings = list(findings)
    return result


def _finding(
    code: str,
    severity: Severity,
    *,
    description: str = "The instruction contract is ambiguous.",
    evidence: str = "PRIVATE RAW PROMPT",
    region: SourceRegion | None = None,
) -> Finding:
    pattern_id = code.split(".", maxsplit=1)[0]
    return Finding(
        pattern_id=pattern_id,
        pattern_name=f"{pattern_id} test rule",
        severity=severity,
        location="system_prompt",
        description=description,
        suggestion="State one explicit contract.",
        evidence=evidence,
        sub_id=code if code != pattern_id else "",
        source_region=region,
    )


def _document(results: dict[str, ScanResult], root: str | Path) -> dict:
    return json.loads(format_sarif(results, repository_root=root))


def test_empty_findings_emit_one_valid_sarif_run(tmp_path):
    source = tmp_path / "clean.yaml"
    document = _document({str(source): _result(source)}, tmp_path)

    assert document["version"] == "2.1.0"
    assert document["$schema"] == SARIF_SCHEMA_URI
    assert len(document["runs"]) == 1
    run = document["runs"][0]
    assert run["tool"]["driver"]["name"] == "LintLang"
    assert run["tool"]["driver"]["rules"] == []
    assert run["results"] == []


def test_representative_documents_validate_against_hash_frozen_oasis_schema(tmp_path):
    schema_bytes = SCHEMA_PATH.read_bytes()
    assert hashlib.sha256(schema_bytes).hexdigest() == OASIS_SCHEMA_SHA256
    validator = Draft4Validator(json.loads(schema_bytes))
    source = tmp_path / "agent.yaml"
    documents = [
        _document({str(source): _result(source)}, tmp_path),
        _document(
            {
                str(source): _result(
                    source,
                    *(
                        _finding(f"H{index}", severity)
                        for index, severity in enumerate(Severity, start=1)
                    ),
                )
            },
            tmp_path,
        ),
        _document({str(source): _result(source, input_error="File not found")}, tmp_path),
    ]

    for document in documents:
        validator.validate(document)


@pytest.mark.parametrize(
    ("severity", "level"),
    [
        (Severity.CRITICAL, "error"),
        (Severity.HIGH, "error"),
        (Severity.MEDIUM, "warning"),
        (Severity.LOW, "note"),
        (Severity.INFO, "note"),
    ],
)
def test_severity_mapping_and_specific_rule_id(tmp_path, severity, level):
    source = tmp_path / "agent.yaml"
    document = _document({str(source): _result(source, _finding("H1.6", severity))}, tmp_path)

    [result] = document["runs"][0]["results"]
    assert result["ruleId"] == "H1.6"
    assert result["level"] == level


def test_rules_and_results_are_deterministic_and_do_not_expose_evidence(tmp_path):
    alpha = tmp_path / "alpha.yaml"
    zeta = tmp_path / "zeta.yaml"
    results = {
        str(zeta): _result(zeta, _finding("H6", Severity.LOW), _finding("H2", Severity.HIGH)),
        str(alpha): _result(alpha, _finding("H1.6", Severity.MEDIUM)),
    }

    first = format_sarif(results, repository_root=tmp_path)
    second = format_sarif(dict(reversed(list(results.items()))), repository_root=tmp_path)

    assert first == second
    assert "PRIVATE RAW PROMPT" not in first
    document = json.loads(first)
    run = document["runs"][0]
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == ["H1.6", "H2", "H6"]
    assert [(item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], item["ruleId"]) for item in run["results"]] == [
        ("alpha.yaml", "H1.6"),
        ("zeta.yaml", "H2"),
        ("zeta.yaml", "H6"),
    ]


def test_duplicate_rule_descriptors_are_canonical_across_input_permutations(tmp_path):
    alpha = tmp_path / "alpha.yaml"
    zeta = tmp_path / "zeta.yaml"
    alpha_finding = _finding("H2", Severity.HIGH)
    alpha_finding.pattern_name = "Alpha descriptor"
    zeta_finding = _finding("H2", Severity.HIGH)
    zeta_finding.pattern_name = "Zeta descriptor"
    forward = {
        str(zeta): _result(zeta, zeta_finding),
        str(alpha): _result(alpha, alpha_finding),
    }
    reverse = dict(reversed(list(forward.items())))

    first = format_sarif(forward, repository_root=tmp_path)
    second = format_sarif(reverse, repository_root=tmp_path)

    assert first == second
    [rule] = json.loads(first)["runs"][0]["tool"]["driver"]["rules"]
    assert rule["shortDescription"]["text"] == "Alpha descriptor"


def test_artifact_uris_are_repository_relative_posix_and_uri_encoded(tmp_path):
    source = tmp_path / "dir with space" / "pr\N{LATIN SMALL LETTER U WITH DIAERESIS}fen.yaml"
    source.parent.mkdir()
    source.write_text("system_prompt: ambiguous", encoding="utf-8")

    rendered = format_sarif(
        {str(source): _result(source, _finding("H2", Severity.HIGH))},
        repository_root=tmp_path,
    )

    [result] = json.loads(rendered)["runs"][0]["results"]
    uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "dir%20with%20space/pr%C3%BCfen.yaml"
    assert str(tmp_path) not in rendered


def test_windows_shaped_paths_are_relativized_without_drive_leakage():
    assert repository_artifact_uri(
        r"C:\checkout\configs\agent.yaml",
        repository_root=r"C:\checkout",
    ) == "configs/agent.yaml"


@pytest.mark.parametrize(
    "source",
    [
        r"..\secret.yaml",
        r"C:\checkout\nested\..\..\secret.yaml",
    ],
)
def test_windows_parent_traversal_is_rejected(source):
    with pytest.raises(ValueError, match="inside the repository root"):
        repository_artifact_uri(source, repository_root=r"C:\checkout")


def test_symlink_reports_the_repository_relative_target(tmp_path):
    if os.name == "nt":
        pytest.skip("symlink creation requires platform-specific privileges on Windows")
    target = tmp_path / "real" / "agent.yaml"
    target.parent.mkdir()
    target.write_text("system_prompt: ambiguous", encoding="utf-8")
    link = tmp_path / "agent-link.yaml"
    link.symlink_to(target)

    assert repository_artifact_uri(link, repository_root=tmp_path) == "real/agent.yaml"


def test_symlink_resolving_outside_root_is_rejected_without_path_fallback(tmp_path):
    if os.name == "nt":
        pytest.skip("symlink creation requires platform-specific privileges on Windows")
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.yaml"
    outside.write_text("system_prompt: ambiguous", encoding="utf-8")
    link = repository / "agent.yaml"
    link.symlink_to(outside)

    with pytest.raises(ValueError, match="inside the repository root"):
        repository_artifact_uri(link, repository_root=repository)


def test_only_evidence_supported_python_lines_create_a_region(tmp_path):
    structured = tmp_path / "agent.yaml"
    python_source = tmp_path / "pipeline.py"
    results = {
        str(structured): _result(structured, _finding("H2", Severity.HIGH)),
        str(python_source): _result(
            python_source,
            _finding("P2", Severity.MEDIUM, region=SourceRegion(start_line=7, end_line=11)),
        ),
    }

    by_rule = {item["ruleId"]: item for item in _document(results, tmp_path)["runs"][0]["results"]}
    structured_location = by_rule["H2"]["locations"][0]["physicalLocation"]
    python_location = by_rule["P2"]["locations"][0]["physicalLocation"]
    assert "region" not in structured_location
    assert python_location["region"] == {"startLine": 7, "endLine": 11}


def test_ast_provenance_carries_separate_p1_p2_and_extracted_h_regions(tmp_path):
    source = tmp_path / "pipeline-unicode.py"
    source.write_text(
        'CONFIDENCE_THRESHOLD = 0.75\n'
        'PROMPT = """\n'
        "You are a careful assistant.\n"
        "Respond in JSON and Markdown.\n"
        + ("Always analyze the user request and return a complete answer. " * 8)
        + '\n"""\n',
        encoding="utf-8",
    )
    scan_result = scan_file(source)

    document = _document({str(source): scan_result}, tmp_path)
    by_rule: dict[str, list[dict]] = {}
    for result in document["runs"][0]["results"]:
        by_rule.setdefault(result["ruleId"], []).append(result)

    [p1] = by_rule["P1"]
    [p2] = by_rule["P2"]
    assert p1["locations"][0]["physicalLocation"]["region"] == {"startLine": 1}
    assert p2["locations"][0]["physicalLocation"]["region"] == {
        "startLine": 2,
        "endLine": 6,
    }
    assert all(
        result["locations"][0]["physicalLocation"]["region"]
        == {"startLine": 2, "endLine": 6}
        for result in by_rule["H6"]
    )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        (
            "duplicate-keys.yaml",
            "system_prompt: first value\n"
            "system_prompt: Respond in JSON and Markdown. Respond in JSON and Markdown.\n",
        ),
        (
            "repeated.json",
            '{"system_prompt":"Respond in JSON and Markdown. Respond in JSON and Markdown."}',
        ),
        (
            "multiline-unicode.yaml",
            "system_prompt: |\n  Be careful with caf\N{LATIN SMALL LETTER E WITH ACUTE} input.\n"
            "  Respond in JSON and Markdown.\n",
        ),
        (
            "aliases.yaml",
            "description: &shared Handle and process data.\n"
            "tools:\n"
            "  - name: first\n    description: *shared\n"
            "  - name: second\n    description: *shared\n",
        ),
    ],
)
def test_structured_parser_edge_cases_never_fabricate_regions(tmp_path, name, content):
    source = tmp_path / "configs with spaces" / name
    source.parent.mkdir(exist_ok=True)
    source.write_text(content, encoding="utf-8")
    scan_result = scan_file(source)
    assert scan_result.structural_findings

    results = _document({str(source): scan_result}, tmp_path)["runs"][0]["results"]

    assert results
    assert all("region" not in result["locations"][0]["physicalLocation"] for result in results)


def test_input_errors_are_execution_failures_not_clean_results(tmp_path):
    missing = tmp_path / "private" / "missing.yaml"
    rendered = format_sarif(
        {str(missing): _result(missing, input_error="File not found")},
        repository_root=tmp_path,
    )

    assert str(tmp_path) not in rendered
    run = json.loads(rendered)["runs"][0]
    assert run["results"] == []
    assert run["invocations"][0]["executionSuccessful"] is False
    [notification] = run["invocations"][0]["toolExecutionNotifications"]
    assert notification["level"] == "error"
    assert "File not found" in notification["message"]["text"]


def test_input_error_outside_root_is_rejected_without_exposing_parser_evidence(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "private.yaml"
    private_value = "PRIVATE_PROMPT_EVIDENCE"
    outside.write_text(f"system_prompt: {private_value}\n  invalid", encoding="utf-8")
    parser_error = f"Failed to parse: while parsing {outside}\n  system_prompt: {private_value}"
    results = {str(outside): _result(outside, input_error=parser_error)}

    prepared, errors = prepare_sarif_results(results, repository_root=repository)
    rendered = format_sarif(prepared, repository_root=repository)

    assert errors == ["SARIF sources must be inside the repository root"]
    assert private_value not in rendered
    assert str(outside) not in rendered
    [notification] = json.loads(rendered)["runs"][0]["invocations"][0][
        "toolExecutionNotifications"
    ]
    assert notification["message"]["text"] == "SARIF sources must be inside the repository root"


def test_parser_input_error_inside_root_does_not_expose_source_evidence(tmp_path):
    source = tmp_path / "agent.yaml"
    private_value = "PRIVATE_PROMPT_EVIDENCE"
    parser_error = f"Failed to parse: mapping error\n  system_prompt: {private_value}"

    rendered = format_sarif(
        {str(source): _result(source, input_error=parser_error)},
        repository_root=tmp_path,
    )

    assert private_value not in rendered
    [notification] = json.loads(rendered)["runs"][0]["invocations"][0][
        "toolExecutionNotifications"
    ]
    assert notification["message"]["text"] == "Input could not be parsed"
