"""Contract tests for the root Gemini CLI extension."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lintlang import __version__

ROOT = Path(__file__).parents[1]
HANDLER = ROOT / "hooks/lintlang_after_tool.py"


def _run_hook(path: Path, *, tool_name: str = "replace", error: str | None = None) -> dict:
    event = {
        "session_id": "test-session",
        "transcript_path": "/tmp/test-session.json",
        "cwd": str(path.parent),
        "hook_event_name": "AfterTool",
        "timestamp": "2026-09-03T00:00:00Z",
        "tool_name": tool_name,
        "tool_input": {"file_path": path.name},
        "tool_response": {"llmContent": "changed", "returnDisplay": "changed", "error": error},
    }
    completed = subprocess.run(
        [sys.executable, str(HANDLER)],
        input=json.dumps(event),
        capture_output=True,
        check=True,
        text=True,
        env=os.environ.copy(),
    )
    return json.loads(completed.stdout)


def test_root_extension_declares_stable_bounded_hook_contract() -> None:
    manifest = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    definition = config["hooks"]["AfterTool"][0]
    hook = definition["hooks"][0]

    assert manifest["name"] == "lintlang"
    assert manifest["version"] == __version__
    assert definition["matcher"] == "^(write_file|replace)$"
    assert hook["timeout"] == 30_000
    assert "${extensionPath}" in hook["command"]
    assert "PyYAML==6.0.3" in hook["command"]


def test_after_tool_returns_bounded_actionable_context(tmp_path: Path) -> None:
    target = tmp_path / "agent.yaml"
    target.write_text("tools:\n  - name: lookup\n    description: Get data\n", encoding="utf-8")

    output = _run_hook(target)

    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "AfterTool"
    assert "agent.yaml" in specific["additionalContext"]
    assert "Suggested repair:" in specific["additionalContext"]
    assert "evidence" not in specific["additionalContext"].lower()


def test_after_tool_is_silent_for_unsupported_file(tmp_path: Path) -> None:
    target = tmp_path / "module.js"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    assert _run_hook(target, tool_name="write_file") == {}


def test_after_tool_is_silent_when_tool_failed(tmp_path: Path) -> None:
    target = tmp_path / "agent.yaml"
    target.write_text("tools: []\n", encoding="utf-8")

    assert _run_hook(target, error="write failed") == {}
