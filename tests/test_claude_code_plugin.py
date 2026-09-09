"""Contract tests for the native Claude Code plugin adapter."""

from __future__ import annotations

import importlib.util
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
    # Pinned to the literal, not only to plugin.json: a coordinated rename of
    # both would keep this green while the documented `lintlang@lintlang`
    # silently stopped resolving.
    assert entry["name"] == "lintlang" == plugin["name"]

    source = ROOT / entry["source"]
    assert source.is_dir()
    assert (source / ".claude-plugin/plugin.json").is_file()
    assert (source / "hooks/hooks.json").is_file()


def test_marketplace_entry_does_not_restate_a_drifting_plugin_version() -> None:
    """The plugin manifest owns the version; a second copy could disagree."""
    entry = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"][0]

    assert "version" not in entry


def _handler_module():
    """Import the hook handler by path, the way Claude Code executes it."""
    spec = importlib.util.spec_from_file_location("lintlang_post_tool_use", HANDLER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_module_route_keeps_the_project_directory_off_sys_path() -> None:
    """`-m` would otherwise import from whatever project the hook fired in."""
    handler = _handler_module()

    assert handler._isolated_env()["PYTHONSAFEPATH"] == "1"

    command = handler._module_command()
    if handler.SAFE_PATH_SUPPORTED:
        assert command is not None
        assert "-P" in command
        assert command.index("-P") < command.index("-m")
    else:
        # Nothing can drop the cwd entry on this interpreter, so the module
        # route is not offered at all and the installed executable is used.
        assert command is None


def test_isolation_flags_actually_drop_the_working_directory(tmp_path: Path) -> None:
    """Benign fixture: a uniquely named module, shadowing nothing.

    It only demonstrates whether `-m` resolves modules out of the working
    directory the hook was invoked in. No real module is shadowed and nothing
    is overridden.
    """
    handler = _handler_module()
    probe = "lintlang_cwd_isolation_probe"
    (tmp_path / f"{probe}.py").write_text("print('loaded from cwd')\n", encoding="utf-8")

    def _resolved_from_cwd(args: tuple[str, ...], env: dict[str, str]) -> bool:
        completed = subprocess.run(
            [sys.executable, *args, "-m", probe],
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
            env=env,
        )
        return completed.returncode == 0 and "loaded from cwd" in completed.stdout

    plain = os.environ.copy()
    plain.pop("PYTHONSAFEPATH", None)

    # Without isolation, `-m` runs code out of the project directory.
    assert _resolved_from_cwd((), plain) is True
    # With the flags the handler uses, it does not.
    assert _resolved_from_cwd(handler.SAFE_PATH_ARGS, handler._isolated_env()) is False


def test_executable_is_preferred_over_the_module_route() -> None:
    """The installed console script never resolves against the project cwd."""
    handler = _handler_module()
    handler.shutil.which = lambda _name: "/usr/local/bin/lintlang"
    handler._is_pinned = lambda command: True

    assert handler._lintlang_command() == ["/usr/local/bin/lintlang"]
