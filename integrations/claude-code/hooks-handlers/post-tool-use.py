#!/usr/bin/env python3
"""Claude Code PostToolUse adapter for LintLang."""

from __future__ import annotations

import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".json", ".md", ".prompt", ".py", ".txt", ".yaml", ".yml"}
MAX_FINDINGS = 8
PINNED_VERSION = "0.5.2"


def _emit(context: str | None = None) -> None:
    output: dict[str, Any] = {}
    if context:
        output["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    print(json.dumps(output))


def _is_pinned(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            [*command, "--version"], capture_output=True, check=False, text=True, timeout=3
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip() == f"lintlang {PINNED_VERSION}"


def _lintlang_command() -> list[str] | None:
    if importlib.util.find_spec("lintlang") is not None:
        module_command = [sys.executable, "-m", "lintlang"]
        if _is_pinned(module_command):
            return module_command
    executable = shutil.which("lintlang")
    if executable and _is_pinned([executable]):
        return [executable]
    return None


def _format_result(path: Path, result: dict[str, Any]) -> str | None:
    input_error = result.get("input_error")
    if input_error:
        return f"LintLang could not scan {path}: {input_error}"

    findings = result.get("structural_findings") or []
    if not findings:
        return None

    lines = [
        f"LintLang found {len(findings)} issue(s) in {path} (verdict: {result.get('verdict', 'unknown')}).",
        "Repair the applicable findings, then keep the user's requested behavior intact:",
    ]
    for finding in findings[:MAX_FINDINGS]:
        code = finding.get("code") or finding.get("pattern_id") or "LintLang"
        severity = str(finding.get("severity", "unknown")).upper()
        location = finding.get("location") or "file"
        description = finding.get("description") or "Issue detected."
        suggestion = finding.get("suggestion")
        line = f"- [{severity} {code}] {location}: {description}"
        if suggestion:
            line += f" Suggested repair: {suggestion}"
        lines.append(line)
    if len(findings) > MAX_FINDINGS:
        lines.append(
            f"- {len(findings) - MAX_FINDINGS} additional finding(s) omitted; "
            f"run `lintlang scan -- {shlex.quote(str(path))}` for all details."
        )
    return "\n".join(lines)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        _emit()
        return 0

    tool_input = event.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str):
        raw_path = (event.get("tool_response") or {}).get("filePath")
    if not isinstance(raw_path, str):
        _emit()
        return 0

    path = Path(raw_path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES or not path.is_file():
        _emit()
        return 0

    command = _lintlang_command()
    if command is None:
        _emit(
            f"LintLang could not check the changed file because lintlang {PINNED_VERSION} is not available. "
            f"Install it with `pipx install lintlang=={PINNED_VERSION}`, then retry the edit or run "
            "`lintlang scan <file>`."
        )
        return 0

    try:
        completed = subprocess.run(
            [*command, "scan", "--format", "json", "--", str(path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
        payload = json.loads(completed.stdout)
        result = payload[0] if isinstance(payload, list) and payload else None
        if not isinstance(result, dict):
            raise ValueError("LintLang returned no file result")
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        _emit(
            f"LintLang could not check {path}: {error}. "
            f"Run `lintlang scan -- {shlex.quote(str(path))}` directly for diagnostics."
        )
        return 0

    _emit(_format_result(path, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
