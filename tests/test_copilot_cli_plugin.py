"""Contracts for the directly installable GitHub Copilot CLI skill plugin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from lintlang import __version__

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "integrations/copilot-cli"
SKILL = PLUGIN / "skills/lintlang-audit/SKILL.md"


def test_copilot_plugin_has_portable_root_manifest_and_skill() -> None:
    manifest = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "lintlang"
    assert manifest["author"]["name"] == "Hermes Labs"
    assert manifest["license"] == "Apache-2.0"
    assert set(manifest) <= {
        "$schema", "name", "version", "description", "author", "homepage",
        "repository", "license", "keywords", "extensions",
    }
    assert SKILL.is_file()
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_metadata, body = text.split("---\n", 2)
    metadata = yaml.safe_load(raw_metadata)
    assert metadata["name"] == SKILL.parent.name == "lintlang-audit"
    assert "Python 3.10+" in metadata["compatibility"]
    assert "--format json -- <file>" in body
    assert f"uvx --from lintlang=={__version__}" in body


def test_copilot_install_path_and_scanner_prerequisite_are_documented() -> None:
    guide = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "copilot plugin install hermes-labs-ai/lintlang:integrations/copilot-cli" in guide
    assert "`/skills list`" in guide
    assert f"python -m pip install lintlang=={__version__}" in guide
    assert "../integrations/copilot-cli/README.md" in (ROOT / "docs/integrations.md").read_text(encoding="utf-8")
    root_skill = (ROOT / ".agents/skills/lintlang/SKILL.md").read_text(encoding="utf-8")
    assert "license: Apache-2.0" in root_skill
    assert "Requires Python 3.10+" in root_skill


def test_packaged_skill_scan_command_reports_a_real_finding(tmp_path: Path) -> None:
    target = tmp_path / "tool.yaml"
    target.write_text('tools:\n  - name: process_ticket\n    description: ""\n', encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "lintlang", "scan", "--format", "json", "--", str(target)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    reports = json.loads(result.stdout)
    assert len(reports) == 1
    report = reports[0]
    assert report["verdict"] == "FAIL"
    assert any(finding["code"] == "H1.1" for finding in report["structural_findings"])
