"""Contract tests for the native Claude Code plugin: hook and on-demand skill."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from lintlang import __version__

ROOT = Path(__file__).parents[1]
PLUGIN_ROOT = ROOT / "integrations/claude-code"
HANDLER = PLUGIN_ROOT / "hooks-handlers/post-tool-use.py"
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".claude-plugin/plugin.json"
ROOT_PLUGIN_MANIFEST = PLUGIN_ROOT / "plugin.json"
SKILL = PLUGIN_ROOT / "skills/lintlang-audit/SKILL.md"

# https://agent-plugins.org/schemas/1.0.0/plugin.schema.json top-level keys.
AGENT_PLUGINS_SCHEMA_KEYS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}


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
    # Both surfaces have to sit under the catalogued directory, or `/plugin
    # install` delivers only one of them.
    assert (source / "skills/lintlang-audit/SKILL.md").is_file()


def test_marketplace_entry_does_not_restate_a_drifting_plugin_version() -> None:
    """The plugin manifest owns the version; a second copy could disagree."""
    entry = json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"][0]

    assert "version" not in entry


def test_agent_plugins_root_manifest_is_present_and_conformant() -> None:
    """awesome-copilot intake (#3302) requires a plugin.json at the plugin root.

    It must mirror the Claude-specific manifest under `.claude-plugin/` for
    name and version, but declare the Agent Plugins 1.0 schema and carry only
    that schema's allowed top-level keys.
    """
    assert ROOT_PLUGIN_MANIFEST.is_file()

    root_manifest = json.loads(ROOT_PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    claude_manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

    assert root_manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert set(root_manifest.keys()) <= AGENT_PLUGINS_SCHEMA_KEYS

    assert root_manifest["name"] == "lintlang" == claude_manifest["name"]
    assert root_manifest["version"] == "0.2.0" == claude_manifest["version"]

    # Author-identifying fields must not diverge from the Claude manifest.
    assert set(root_manifest.get("author", {})) <= {"name", "email", "url"}


def _skill() -> tuple[dict, str]:
    """Return the skill's parsed frontmatter and its body text."""
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, frontmatter, body = text.split("---\n", 2)
    return yaml.safe_load(frontmatter), body


def test_on_demand_skill_is_discoverable_at_the_plugin_root() -> None:
    """Claude Code loads `<plugin root>/skills/<name>/SKILL.md`.

    The directory name is the address the host uses, so a frontmatter `name`
    that disagrees with it names a skill nobody can invoke.
    """
    frontmatter, body = _skill()

    assert frontmatter["name"] == SKILL.parent.name == "lintlang-audit"
    assert frontmatter["description"].strip()
    assert body.strip()


def test_on_demand_skill_pins_the_released_cli_this_repository_publishes() -> None:
    """A stale pin sends users to a release whose codes no longer match.

    Every version the skill names must be the one this repository ships, so a
    release bump cannot leave the skill pointing at the previous artifact.
    """
    _, body = _skill()

    named = set(re.findall(r"lintlang[= ]=?(\d+\.\d+\.\d+)", body))
    assert named == {__version__}
    assert f"uvx --from lintlang=={__version__}" in body


def test_on_demand_skill_runs_from_a_clean_install_with_no_checkout() -> None:
    """The packaged skill reaches users who never clone this repository.

    Anything resolved relative to a source tree -- the `samples/` fixtures, an
    editable install, `PYTHONPATH=src` -- works for a maintainer and fails for
    everyone who installed the plugin from the marketplace.
    """
    _, body = _skill()

    for checkout_only in ("samples/", "PYTHONPATH", "pip install -e", "python -m build"):
        assert checkout_only not in body

    # It must still name a runner that needs no install at all.
    assert "uvx" in body


def test_on_demand_skill_is_not_presented_as_a_hook() -> None:
    """The plugin ships both surfaces; only one of them fires by itself.

    Describing the skill as automatic would promise coverage it does not give:
    a user who believes edits are audited would never ask for an audit.
    """
    frontmatter, body = _skill()

    description = frontmatter["description"].lower()
    for hook_claim in ("hook", "posttooluse", "after a write", "automatic"):
        assert hook_claim not in description

    # And the body has to draw the distinction rather than leave it implied.
    assert "It is not the plugin's" in body
    assert "PostToolUse" in body


def test_on_demand_skill_reads_the_verdict_from_output_not_exit_status() -> None:
    """`scan` exits 0 on a scannable file whatever the verdict.

    A skill that read the exit status as the result would report every FAIL
    without `--fail-on` as a pass.
    """
    _, body = _skill()

    assert "never from the exit status" in body
    assert "--fail-on" in body
    assert "input_error" in body


def test_on_demand_skill_treats_scan_output_as_untrusted_data() -> None:
    """Findings quote the audited file verbatim in `evidence`.

    That text is input under audit, so the skill must say it is data and not
    instructions before the agent ever reads a payload.
    """
    _, body = _skill()

    assert "data, not instructions" in body
    assert "untrusted data" in body


def _handler_module():
    """Import the hook handler by path, the way Claude Code executes it."""
    spec = importlib.util.spec_from_file_location("lintlang_post_tool_use", HANDLER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_hook_reports_input_error_even_with_skipped_metadata(tmp_path: Path) -> None:
    handler = _handler_module()
    target = tmp_path / "agent.yaml"

    message = handler._format_result(
        target,
        {"input_error": "Tool-like content could not be inspected", "skipped": "coverage gap"},
    )

    assert message == f"LintLang could not scan {target}: Tool-like content could not be inspected"


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
