"""Contract tests for Cursor marketplace discovery of the portable audit skill."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
MARKETPLACE = ROOT / ".cursor-plugin/marketplace.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cursor_marketplace_resolves_the_existing_agent_plugin() -> None:
    marketplace = _json(MARKETPLACE)
    assert marketplace["name"] == "lintlang"
    assert marketplace["owner"]["name"] == "Hermes Labs"

    entries = marketplace["plugins"]
    assert len(entries) == 1
    entry = entries[0]
    plugin_root = ROOT / entry["source"]

    assert entry["name"] == "lintlang"
    assert plugin_root.is_dir()
    assert (plugin_root / "plugin.json").is_file()
    assert (plugin_root / "skills/lintlang-audit/SKILL.md").is_file()


def test_cursor_wrapper_reuses_the_portable_skill_without_claiming_the_hook() -> None:
    plugin_root = ROOT / "integrations/claude-code"
    cursor = _json(plugin_root / ".cursor-plugin/plugin.json")
    portable = _json(plugin_root / "plugin.json")

    assert cursor["name"] == portable["name"] == "lintlang"
    assert cursor["version"] == portable["version"]
    assert cursor["author"] == portable["author"]
    assert cursor["skills"] == "skills/*/SKILL.md"
    assert "hooks" not in cursor

    skill_files = list(plugin_root.glob(cursor["skills"]))
    assert skill_files == [plugin_root / "skills/lintlang-audit/SKILL.md"]

    logo = plugin_root / cursor["logo"]
    assert logo.is_file()
    assert logo.resolve().is_relative_to(plugin_root.resolve())
