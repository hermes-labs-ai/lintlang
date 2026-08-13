"""Deterministic SARIF 2.1.0 serialization for repository scans."""

from __future__ import annotations

import json
import ntpath
import re
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from urllib.parse import quote

from . import __version__
from .patterns import Finding, Severity
from .scanner import ScanResult, input_error_result

SARIF_SCHEMA_URI = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/"
    "schemas/sarif-schema-2.1.0.json"
)

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_LEVELS = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}


class SarifLocationError(ValueError):
    """Raised when a source cannot be represented as a repository URI."""


def find_repository_root(start: str | Path) -> Path:
    """Find the nearest Git worktree root, falling back to the start directory."""
    current = Path(start).resolve(strict=False)
    if not current.is_dir():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _windows_relative(source: str, root: str, source_base: str | None) -> str:
    root_path = PureWindowsPath(ntpath.normpath(root))
    base_path = PureWindowsPath(ntpath.normpath(source_base or root))
    source_path = PureWindowsPath(source)
    if not source_path.is_absolute():
        source_path = base_path / source_path
    source_path = PureWindowsPath(ntpath.normpath(str(source_path)))
    try:
        relative = source_path.relative_to(root_path)
    except ValueError as error:
        raise SarifLocationError("SARIF sources must be inside the repository root") from error
    return relative.as_posix()


def repository_artifact_uri(
    source: str | Path,
    *,
    repository_root: str | Path,
    source_base: str | Path | None = None,
) -> str:
    """Return a URI-encoded, repository-relative POSIX artifact URI.

    Existing POSIX symlinks resolve to their target because GitHub cannot map
    a reported symlink path to a committed source file. Sources outside the
    selected root are rejected instead of leaking or fabricating a path.
    """
    source_text = str(source)
    root_text = str(repository_root)
    if _WINDOWS_ABSOLUTE.match(source_text) or _WINDOWS_ABSOLUTE.match(root_text):
        relative = _windows_relative(
            source_text,
            root_text,
            str(source_base) if source_base is not None else None,
        )
    else:
        root_path = Path(repository_root).resolve(strict=False)
        base_path = Path(source_base).resolve(strict=False) if source_base is not None else root_path
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = base_path / source_path
        source_path = source_path.resolve(strict=False)
        try:
            relative = source_path.relative_to(root_path).as_posix()
        except ValueError as error:
            raise SarifLocationError("SARIF sources must be inside the repository root") from error
    if not relative or relative == ".":
        raise SarifLocationError("SARIF sources must identify a file inside the repository root")
    return quote(relative, safe="/-._~")


def _message(finding: Finding, show_suggestions: bool) -> str:
    if show_suggestions and finding.suggestion:
        return f"{finding.description} Suggested action: {finding.suggestion}"
    return finding.description


def _rule(finding: Finding) -> dict[str, object]:
    return {
        "id": finding.code,
        "shortDescription": {"text": finding.pattern_name},
    }


def _result(
    finding: Finding,
    artifact_uri: str,
    *,
    show_suggestions: bool,
) -> dict[str, object]:
    physical_location: dict[str, object] = {
        "artifactLocation": {"uri": artifact_uri},
    }
    if finding.source_region is not None:
        region: dict[str, int] = {"startLine": finding.source_region.start_line}
        if finding.source_region.end_line != finding.source_region.start_line:
            region["endLine"] = finding.source_region.end_line
        physical_location["region"] = region
    return {
        "ruleId": finding.code,
        "level": _LEVELS[finding.severity],
        "message": {"text": _message(finding, show_suggestions)},
        "locations": [{"physicalLocation": physical_location}],
    }


def prepare_sarif_results(
    results: Mapping[str, ScanResult],
    *,
    repository_root: str | Path,
    source_base: str | Path | None = None,
) -> tuple[dict[str, ScanResult], list[str]]:
    """Convert unrepresentable sources to per-input errors before serialization."""
    prepared: dict[str, ScanResult] = {}
    errors: list[str] = []
    for path, scan_result in results.items():
        try:
            repository_artifact_uri(
                scan_result.file or path,
                repository_root=repository_root,
                source_base=source_base,
            )
        except SarifLocationError as error:
            message = str(error)
            errors.append(message)
            prepared[path] = input_error_result(scan_result.file or path, message)
            continue
        prepared[path] = scan_result
    return prepared, errors


def _safe_input_error(message: str) -> str:
    """Map scanner failures to stable SARIF notifications without source evidence."""
    if message == "File not found":
        return message
    if message.startswith("Failed to parse:"):
        return "Input could not be parsed"
    if message.startswith("File scan requires a file:"):
        return "Input is not a regular file"
    if message.startswith("Failed to traverse:"):
        return "Input directory could not be traversed"
    if message.startswith("SARIF sources must"):
        return message
    return "Input could not be inspected"


def format_sarif(
    results: Mapping[str, ScanResult],
    *,
    repository_root: str | Path,
    source_base: str | Path | None = None,
    show_suggestions: bool = True,
) -> str:
    """Serialize scan results as canonical, evidence-minimal SARIF JSON."""
    rules: dict[str, dict[str, object]] = {}
    sarif_results: list[tuple[tuple[object, ...], dict[str, object]]] = []
    errors: list[str] = []

    for path, scan_result in results.items():
        if scan_result.input_error is not None:
            errors.append(_safe_input_error(scan_result.input_error))
            continue
        try:
            artifact_uri = repository_artifact_uri(
                scan_result.file or path,
                repository_root=repository_root,
                source_base=source_base,
            )
        except SarifLocationError as error:
            errors.append(str(error))
            continue
        for finding in scan_result.structural_findings:
            candidate_rule = _rule(finding)
            existing_rule = rules.get(finding.code)
            if existing_rule is None or json.dumps(candidate_rule, sort_keys=True) < json.dumps(
                existing_rule, sort_keys=True
            ):
                rules[finding.code] = candidate_rule
            item = _result(finding, artifact_uri, show_suggestions=show_suggestions)
            region = finding.source_region
            sort_key = (
                artifact_uri,
                region.start_line if region else 0,
                region.end_line if region else 0,
                finding.code,
                finding.description,
                finding.suggestion if show_suggestions else "",
            )
            sarif_results.append((sort_key, item))

    if not results:
        errors.append("No files were successfully scanned")

    invocation: dict[str, object] = {"executionSuccessful": not errors}
    if errors:
        invocation["toolExecutionNotifications"] = [
            {
                "descriptor": {"id": "LL_INPUT_ERROR"},
                "level": "error",
                "message": {"text": error},
            }
            for error in sorted(errors)
        ]

    document = {
        "$schema": SARIF_SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "LintLang",
                        "informationUri": "https://github.com/hermes-labs-ai/lintlang",
                        "semanticVersion": __version__,
                        "rules": [rules[rule_id] for rule_id in sorted(rules)],
                    }
                },
                "invocations": [invocation],
                "results": [item for _, item in sorted(sarif_results, key=lambda pair: pair[0])],
            }
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def format_sarif_error(message: str) -> str:
    """Return a valid SARIF envelope that unambiguously records a fatal output error."""
    document = json.loads(format_sarif({}, repository_root=Path.cwd()))
    notification = document["runs"][0]["invocations"][0]["toolExecutionNotifications"][0]
    notification["message"]["text"] = message
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
