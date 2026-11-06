"""Contracts for the zero-touch automation assets."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PROOF_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "proof-benchmark.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
RETIRED_RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-sync.yml"
RELEASE_NOTES = REPO_ROOT / ".github" / "releases" / "v0.8.3.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
README = REPO_ROOT / "README.md"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync-version-docs.py"


def load_sync_script():
    spec = importlib.util.spec_from_file_location("sync_version_docs", SYNC_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_version_docs"] = module
    spec.loader.exec_module(module)
    return module


def project_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match
    return match.group(1)


def test_proof_workflow_is_nightly_clean_timed_and_sarif_backed():
    text = PROOF_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    job = workflow["jobs"]["fail-fix-pass"]

    assert 'cron: "17 8 * * *"' in text
    assert "branches: [main]" in text
    assert job["timeout-minutes"] == 5
    checkout = next(step for step in job["steps"] if step.get("name") == "Clean clone")
    assert checkout["with"]["clean"] is True
    assert checkout["with"]["persist-credentials"] is False
    loop = next(step["run"] for step in job["steps"] if step.get("name") == "Run fail, fix, pass proof loop")
    assert "limit_seconds = 300.0" in loop
    assert '"fail.sarif"' in loop
    assert '"pass.sarif"' in loop
    assert '"--fail-on"' in loop
    assert '"fail"' in loop


def test_release_workflow_is_tag_driven_and_publishes_curated_release_once():
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    jobs = workflow["jobs"]

    assert 'tags:\n      - "v*"' in text
    assert "workflow_dispatch:" in text
    assert not RETIRED_RELEASE_WORKFLOW.exists()
    assert set(jobs) == {"build", "github-release", "publish"}
    assert all(
        job.get("permissions", {}).get("contents") != "write"
        for name, job in jobs.items()
        if name != "github-release"
    )
    build_run = "\n".join(str(step.get("run", "")) for step in jobs["build"]["steps"])
    release_run = "\n".join(str(step.get("run", "")) for step in jobs["github-release"]["steps"])
    assert "python -m build" in build_run
    assert "python -m twine check --strict dist/*" in build_run
    assert "scripts/sync-version-docs.py" in build_run
    assert "git merge-base --is-ancestor HEAD origin/main" in build_run
    assert "--check" in build_run
    assert "git push" not in text
    assert ".github/releases/${RELEASE_TAG}.md" in build_run
    assert "release-notes.md" in build_run
    assert "release-title.txt" in build_run
    uploads = [
        step
        for step in jobs["build"]["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    assert {step["with"]["name"] for step in uploads} == {
        "release-distributions",
        "release-metadata",
    }
    assert all(step["with"]["overwrite"] is True for step in uploads)
    assert "--notes-file dist/release-notes.md" in release_run
    assert '--title "$release_title"' in release_run
    assert "--generate-notes" not in release_run
    assert "--draft=false" in release_run
    assert release_run.count("gh release create") == 1
    assert "dist/*.tar.gz" in release_run
    pypi = jobs["publish"]
    assert pypi["needs"] == "github-release"
    assert pypi["environment"] == "pypi"
    assert pypi["permissions"] == {"actions": "read", "id-token": "write"}
    assert any(step.get("uses", "").startswith("pypa/gh-action-pypi-publish@") for step in pypi["steps"])
    action_steps = [
        step
        for job in jobs.values()
        for step in job.get("steps", [])
        if "uses" in step
    ]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"]) for step in action_steps)


def test_curated_release_notes_match_the_083_public_contract():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert notes.startswith("# LintLang v0.8.3 — Better agent-file discovery and diagnostics\n")
    assert "`.cursor/rules/*.mdc`" in notes
    assert "Invalid YAML tool names" in notes
    assert "which return a coverage error" in notes
    assert "supported CrewAI" not in notes
    assert "uvx --from lintlang==0.8.3 lintlang scan ." in notes
    assert "No LLM calls during scanning" in notes
    assert "v0.8.2...v0.8.3" in notes
    assert "false positive" not in notes.lower()
    assert "[@Soham-o](https://github.com/Soham-o)" in notes
    assert "/pull/170" in notes
    assert "/pull/174" in notes
    assert "[@yunaremaia](https://github.com/yunaremaia)" in notes
    assert "/pull/179" in notes
    assert "/pull/180" in notes
    assert "bounded NUL-density input-integrity guard" in notes


def test_changelog_keeps_the_encoding_guard_claim_bounded():
    release_section = CHANGELOG.read_text(encoding="utf-8").split("## [0.8.2]", 1)[0]

    assert "Common ASCII-heavy, NUL-dense BOM-less UTF-16 and UTF-32 inputs" in release_section
    assert "bounded 8 KiB prefix" in release_section
    assert "20% or greater NUL" in release_section
    assert "not universal wide-encoding detection" in release_section
    assert "/pull/180" in release_section
    assert release_section.count("[@Soham-o](https://github.com/Soham-o)") == 2
    assert "[@yunaremaia](https://github.com/yunaremaia)" in release_section
    assert "BOM-less UTF-16 and UTF-32 input can no longer" not in release_section


def test_readme_ci_history_claim_stays_within_the_verified_tag_range():
    readme = README.read_text(encoding="utf-8")

    assert "Every tagged release points at a commit with a passing CI run" not in readme
    assert (
        "Every tagged release from v0.3.1 through v0.8.2 points at a commit "
        "with a passing CI run"
    ) in readme


def test_repository_docs_are_already_version_synced():
    result = subprocess.run(
        [
            sys.executable,
            str(SYNC_SCRIPT),
            "--version",
            project_version(),
            "--root",
            str(REPO_ROOT),
            "--check",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_version_sync_does_not_rewrite_unrelated_historical_pins():
    sync = load_sync_script()
    text = (
        "LINTLANG v0.4.1\n"
        "Excerpt from `lintlang 0.4.1`\n"
        "uses: hermes-labs-ai/lintlang@v0.4.1\n"
        "rev: v0.4.1\n"
        "An ecosystem example pins lintlang==0.3.1.\n"
    )
    updated = sync.synchronized(text, "0.5.0")

    assert "LINTLANG v0.5.0" in updated
    assert "`lintlang 0.5.0`" in updated
    assert "lintlang@v0.5.0" in updated
    assert "rev: v0.5.0" in updated
    assert "lintlang==0.3.1" in updated


def test_version_sync_updates_known_current_surfaces_and_preserves_held_pins():
    sync = load_sync_script()

    current = sync.synchronized_release_surface(
        Path("integrations/claude-code/README.md"),
        "uvx --from lintlang==0.8.3 lintlang --version\nversion 0.8.3 or newer\n",
        "0.8.4",
    )
    held = sync.synchronized_release_surface(
        Path("integrations/devcontainer/src/lintlang/README.md"),
        "The intentionally held package is lintlang==0.7.0.\n",
        "0.8.4",
    )
    evidence = sync.synchronized_release_surface(
        Path("docs/integrations.md"),
        "Use `uvx --from lintlang==0.8.3`. Public evidence pins `lintlang==0.3.1`.\n",
        "0.8.4",
    )

    assert "lintlang==0.8.4" in current
    assert "version 0.8.4 or newer" in current
    assert held == "The intentionally held package is lintlang==0.7.0.\n"
    assert evidence == (
        "Use `uvx --from lintlang==0.8.4`. Public evidence pins `lintlang==0.3.1`.\n"
    )


def test_version_sync_checks_the_tag_specific_release_notes(tmp_path):
    sync = load_sync_script()
    notes = tmp_path / ".github" / "releases" / "v0.8.4.md"
    notes.parent.mkdir(parents=True)
    notes.write_text(
        "# LintLang v0.8.3\n\n`uvx --from lintlang==0.8.3 lintlang scan .`\n",
        encoding="utf-8",
    )

    assert notes in sync.release_surfaces(tmp_path, "0.8.4")
    assert sync.main(["--version", "0.8.4", "--root", str(tmp_path), "--check"]) == 1
    assert sync.main(["--version", "0.8.4", "--root", str(tmp_path)]) == 0
    assert notes.read_text(encoding="utf-8") == (
        "# LintLang v0.8.4\n\n`uvx --from lintlang==0.8.4 lintlang scan .`\n"
    )


def test_version_sync_updates_versions_of_record_without_touching_other_fields():
    sync = load_sync_script()

    pyproject = sync.synchronized_release_surface(
        Path("pyproject.toml"),
        '[project]\nname = "lintlang"\nversion = "0.8.3"\n\n[tool.example]\nversion = "1.2.3"\n',
        "0.8.4",
    )
    metadata = sync.synchronized_release_surface(
        Path("codemeta.json"),
        '{\n  "version": "0.8.3",\n  "url": "https://pypi.org/project/lintlang/0.8.3/"\n}\n',
        "0.8.4",
    )

    assert 'version = "0.8.4"' in pyproject
    assert 'version = "1.2.3"' in pyproject
    assert '"version": "0.8.4"' in metadata
    assert "/lintlang/0.8.4/" in metadata
