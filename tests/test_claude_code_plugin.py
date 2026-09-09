"""Contract tests for the native Claude Code plugin adapter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
HANDLER = ROOT / "integrations/claude-code/hooks-handlers/post-tool-use.py"
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
PLUGIN_MANIFEST = ROOT / "integrations/claude-code/.claude-plugin/plugin.json"


def _run_hook(path: Path) -> dict:
    event = {
        "session_id": "test-session",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(path)},
        "tool_response": {"success": True},
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PATH"] = ""
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


def test_repository_is_an_installable_claude_code_marketplace() -> None:
    """Claude Code cannot install a plugin that no marketplace catalogs."""
    manifest = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

    assert manifest["name"] == "lintlang"
    assert manifest["owner"]["name"]
    entries = manifest["plugins"]
    assert len(entries) == 1

    entry = entries[0]
    plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    assert entry["name"] == plugin["name"]

    source = ROOT / entry["source"]
    assert source.is_dir()
    assert (source / ".claude-plugin/plugin.json").is_file()
    assert (source / "hooks/hooks.json").is_file()


def test_marketplace_entry_does_not_restate_a_drifting_plugin_version() -> None:
    """The plugin manifest owns the version; a second copy could disagree."""
    entry = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"][0]

    assert "version" not in entry
