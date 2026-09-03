#!/usr/bin/env python3
"""Gemini CLI AfterTool adapter for the bundled LintLang source."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".json", ".md", ".prompt", ".py", ".txt", ".yaml", ".yml"}
MAX_FINDINGS = 8


def _emit(context: str | None = None) -> None:
    output: dict[str, Any] = {}
    if context:
        output["hookSpecificOutput"] = {
            "hookEventName": "AfterTool",
            "additionalContext": context,
        }
    print(json.dumps(output))


def _display_path(path: Path, cwd: str | None) -> str:
    if cwd:
        try:
            return str(path.resolve().relative_to(Path(cwd).resolve()))
        except ValueError:
            pass
    return str(path)


def _format_result(path: str, verdict: str, result: Any) -> str | None:
    if result.input_error:
        return f"LintLang could not scan {path}: {result.input_error}"
    findings = result.structural_findings
    if not findings:
        return None

    lines = [
        f"LintLang found {len(findings)} issue(s) in {path} (verdict: {verdict}).",
        "Repair the applicable findings, then preserve the user's requested behavior:",
    ]
    for finding in findings[:MAX_FINDINGS]:
        severity = finding.severity.value.upper()
        lines.append(
            f"- [{severity} {finding.code}] {finding.location}: {finding.description} "
            f"Suggested repair: {finding.suggestion}"
        )
    if len(findings) > MAX_FINDINGS:
        omitted = len(findings) - MAX_FINDINGS
        lines.append(f"- {omitted} additional finding(s) omitted; run `lintlang scan {path}` for all details.")
    return "\n".join(lines)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        _emit()
        return 0

    if event.get("hook_event_name") != "AfterTool":
        _emit()
        return 0
    if event.get("tool_name") not in {"write_file", "replace"}:
        _emit()
        return 0
    if (event.get("tool_response") or {}).get("error"):
        _emit()
        return 0

    raw_path = (event.get("tool_input") or {}).get("file_path")
    if not isinstance(raw_path, str):
        _emit()
        return 0

    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    path = Path(raw_path)
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    if path.suffix.lower() not in SUPPORTED_SUFFIXES or not path.is_file():
        _emit()
        return 0

    extension_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(extension_root / "src"))
    display_path = _display_path(path, cwd)
    try:
        from lintlang.report import compute_verdict
        from lintlang.scanner import scan_file

        result = scan_file(path)
        context = _format_result(display_path, compute_verdict(result), result)
    except Exception as error:
        context = f"LintLang could not scan {display_path}: {error}. Run `lintlang scan {display_path}` directly."

    _emit(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
