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

    # The entry duplicates the description so `/plugin` can show it before the
    # plugin is fetched; guard it so the two copies cannot silently diverge.
    assert entry["description"] == plugin["description"]

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
    # The neutral directory is the handler's own; it holds no lintlang module.
    assert HANDLER.parent == handler.NEUTRAL_CWD
    assert not list(handler.NEUTRAL_CWD.glob("lintlang*"))

    # The module route stays available on every supported interpreter; only the
    # extra flag is version-gated.
    command = handler._module_command()
    assert command is not None
    assert command[-2:] == ["-m", "lintlang"]
    if handler.SAFE_PATH_SUPPORTED:
        assert "-P" in command


def test_isolation_actually_drops_the_working_directory(tmp_path: Path) -> None:
    """Benign fixture: a uniquely named module, shadowing nothing.

    It only demonstrates whether `-m` resolves modules out of the directory the
    subprocess runs in. No real module is shadowed and nothing is overridden.
    """
    handler = _handler_module()
    probe = "lintlang_cwd_isolation_probe"
    (tmp_path / f"{probe}.py").write_text("print('loaded from cwd')\n", encoding="utf-8")

    def _resolved_from_project(*, isolated: bool) -> bool:
        env = os.environ.copy()
        env.pop("PYTHONSAFEPATH", None)
        completed = subprocess.run(
            [
                sys.executable,
                *(handler.SAFE_PATH_ARGS if isolated else ()),
                "-m",
                probe,
            ],
            capture_output=True,
            check=False,
            text=True,
            cwd=handler.NEUTRAL_CWD if isolated else tmp_path,
            env=handler._isolated_env() if isolated else env,
        )
        return completed.returncode == 0 and "loaded from cwd" in completed.stdout

    # Running from the edited project, `-m` executes code found there.
    assert _resolved_from_project(isolated=False) is True
    # Running the way the handler does, it does not.
    assert _resolved_from_project(isolated=True) is False


def test_executable_is_preferred_over_the_module_route(monkeypatch) -> None:
    """The installed console script never resolves against the project cwd."""
    handler = _handler_module()
    # `handler.shutil` is the shared sys.modules singleton, so this patch has to
    # be undone at teardown or it leaks into every later test in the session.
    monkeypatch.setattr(handler.shutil, "which", lambda _name: "/usr/local/bin/lintlang")
    monkeypatch.setattr(handler, "_is_pinned", lambda command: True)

    assert handler._lintlang_command() == ["/usr/local/bin/lintlang"]


def test_isolated_env_drops_relative_pythonpath_entries(monkeypatch) -> None:
    """A relative PYTHONPATH entry would put a directory back on sys.path."""
    handler = _handler_module()
    absolute = str(ROOT / "src")

    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([".", absolute, "relative/dir"]))
    assert handler._isolated_env()["PYTHONPATH"] == absolute

    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([".", "relative/dir"]))
    assert "PYTHONPATH" not in handler._isolated_env()
