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
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-sync.yml"
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


def test_release_workflow_is_tag_driven_read_only_and_publishes_a_release():
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    jobs = workflow["jobs"]

    assert 'tags:\n      - "v*"' in text
    assert "workflow_call:" in text
    assert set(jobs) == {"build", "github-release"}
    assert all(
        job.get("permissions", {}).get("contents") != "write"
        for name, job in jobs.items()
        if name != "github-release"
    )
    build_run = "\n".join(str(step.get("run", "")) for step in jobs["build"]["steps"])
    release_run = "\n".join(str(step.get("run", "")) for step in jobs["github-release"]["steps"])
    assert "python -m build --wheel" in build_run
    assert "scripts/sync-version-docs.py" in build_run
    assert "--check" in build_run
    assert "git push" not in text
    assert "--generate-notes" in release_run
    action_steps = [step for job in jobs.values() for step in job["steps"] if "uses" in step]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"]) for step in action_steps)


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
