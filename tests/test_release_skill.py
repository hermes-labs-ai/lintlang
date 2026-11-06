"""The maintainer release skill remains a tiny path into existing automation."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".agents" / "skills" / "lintlang-release" / "SKILL.md"
SYNC = ROOT / "scripts" / "sync-version-docs.py"


def _skill() -> tuple[dict[str, object], str]:
    text = SKILL.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match, "release skill must have one YAML frontmatter block"
    return yaml.safe_load(match.group(1)), match.group(2)


def test_release_skill_is_discoverable_and_progressively_selects_drive_phase():
    frontmatter, body = _skill()

    assert frontmatter["name"] == SKILL.parent.name == "lintlang-release"
    description = str(frontmatter["description"]).lower()
    for trigger in ("prepare", "publish", "resume", "dry-run"):
        assert trigger in description

    document_ids = {
        "1jac3QfhDxnnf9iMWNdLRw0ByL7HgNaUhJ-Jflq37t2Y",
        "1tcXacj0cF07P4EJk1ii7gxvkonqd8eAHenwU7m5ef7g",
        "1K6E_3E8zitQOWJN5k67oFsb0OvEk-eIEyv-UmK9qBNc",
        "1RG3bG204R83X44OfpdspAy2ebFPru_I1PA_9kMKkWA4",
    }
    assert all(document_id in body for document_id in document_ids)
    assert "Then read only the phase" in body


def test_release_skill_reuses_one_mechanical_path_and_one_publisher():
    _, body = _skill()

    assert "scripts/sync-version-docs.py" in body
    assert "scripts/verify_release_tag.py" in body
    assert ".github/workflows/publish.yml" in body
    assert not (ROOT / ".github" / "workflows" / "release-sync.yml").exists()
    assert "gh release create" not in body
    assert "git push" not in body


def test_release_dry_run_reports_repeatable_plan_without_writing(tmp_path):
    files = {
        Path("pyproject.toml"): '[project]\nname = "lintlang"\nversion = "0.8.3"\n',
        Path("src/lintlang/__init__.py"): '__version__ = "0.8.3"\n',
        Path("docs/current.md"): "LINTLANG v0.8.3\n",
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    before = {relative: (tmp_path / relative).read_bytes() for relative in files}
    command = [
        sys.executable,
        str(SYNC),
        "--version",
        "0.8.4",
        "--root",
        str(tmp_path),
        "--check",
    ]

    first = subprocess.run(command, text=True, capture_output=True, check=False)
    second = subprocess.run(command, text=True, capture_output=True, check=False)

    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout == (
        "docs/current.md\npyproject.toml\nsrc/lintlang/__init__.py\n"
    )
    assert {relative: (tmp_path / relative).read_bytes() for relative in files} == before
