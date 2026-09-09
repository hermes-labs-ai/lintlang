#!/usr/bin/env python3
"""Claude Code PostToolUse adapter for LintLang."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".json", ".md", ".prompt", ".py", ".txt", ".yaml", ".yml"}
MAX_FINDINGS = 8
PINNED_VERSION = "0.5.3"

# Claude Code runs hooks with the user's project directory as the working
# directory, and `python3 -m lintlang` prepends the working directory to the
# child's sys.path. A file named lintlang.py (or a lintlang/ package) in the
# opened project would then run instead of the installed linter -- including
# during the `--version` probe, which happens before the pin is compared, so the
# pin cannot prevent it.
#
# Every LintLang subprocess therefore runs from this handler's own directory
# rather than the user's project. That works on every supported interpreter.
# `-P` and PYTHONSAFEPATH, available from 3.11, drop the entry outright and are
# applied as well where they exist.
NEUTRAL_CWD = Path(__file__).resolve().parent
SAFE_PATH_SUPPORTED = sys.version_info >= (3, 11)
SAFE_PATH_ARGS = ("-P",) if SAFE_PATH_SUPPORTED else ()


def _isolated_env() -> dict[str, str]:
    """Return the parent environment with no relative import path.

    `-P` and PYTHONSAFEPATH drop the implicit working-directory entry, but
    neither filters PYTHONPATH: an inherited relative entry such as `.` is
    resolved against the child's working directory and would put a directory
    back on `sys.path`. Absolute entries are the caller's deliberate choice and
    are preserved.
    """
    env = os.environ.copy()
    env["PYTHONSAFEPATH"] = "1"
    python_path = env.get("PYTHONPATH")
    if python_path:
        absolute = [
            entry for entry in python_path.split(os.pathsep) if entry and os.path.isabs(entry)
        ]
        if absolute:
            env["PYTHONPATH"] = os.pathsep.join(absolute)
        else:
            env.pop("PYTHONPATH")
    return env


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
            [*command, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
            cwd=NEUTRAL_CWD,
            env=_isolated_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip() == f"lintlang {PINNED_VERSION}"


def _module_command() -> list[str] | None:
    """Return the `-m lintlang` command, isolated from the user's project."""
    if importlib.util.find_spec("lintlang") is None:
        return None
    return [sys.executable, *SAFE_PATH_ARGS, "-m", "lintlang"]


def _lintlang_command() -> list[str] | None:
    # The installed executable is preferred: its sys.path[0] is its own
    # directory, never the project the hook was invoked in.
    executable = shutil.which("lintlang")
    if executable and _is_pinned([executable]):
        return [executable]
    module_command = _module_command()
    if module_command is not None and _is_pinned(module_command):
        return module_command
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

    # Resolved before the neutral working directory is applied below, so a
    # relative path from the event still names the file the user just edited.
    path = Path(raw_path).resolve()
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
            cwd=NEUTRAL_CWD,
            env=_isolated_env(),
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
