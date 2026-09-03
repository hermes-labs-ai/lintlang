"""Contract tests for the native Claude Code plugin adapter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
HANDLER = ROOT / "integrations/claude-code/hooks-handlers/post-tool-use.py"


def _run_hook(path: Path) -> dict:
    event = {
        "session_id": "test-session",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(path)},
        "tool_response": {"success": True},
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, str(HANDLER)],
        input=json.dumps(event),
        capture_output=True,
        check=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def test_hook_returns_actionable_repair_context_for_findings(tmp_path: Path) -> None:
    target = tmp_path / "agent.yaml"
    target.write_text("tools:\n  - name: lookup\n    description: Get data\n", encoding="utf-8")

    output = _run_hook(target)

    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PostToolUse"
    assert "Suggested repair:" in specific["additionalContext"]
    assert "evidence" not in specific["additionalContext"].lower()


def test_hook_is_silent_for_unsupported_file(tmp_path: Path) -> None:
    target = tmp_path / "module.js"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    assert _run_hook(target) == {}
