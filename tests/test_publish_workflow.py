"""Release workflow and tag/package coherence contracts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish.yml"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_release_tag.py"
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD_ARTIFACT_V7_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD_ARTIFACT_V8_SHA = "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"


def test_release_tag_verifier_accepts_only_matching_v_prefixed_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "example"\nversion = "0.4.0"\n', encoding="utf-8")

    matching = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--tag", "v0.4.0", "--pyproject", str(pyproject)],
        text=True,
        capture_output=True,
        check=False,
    )
    unprefixed = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--tag", "0.4.0", "--pyproject", str(pyproject)],
        text=True,
        capture_output=True,
        check=False,
    )
    mismatched = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--tag", "v0.3.8", "--pyproject", str(pyproject)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert matching.returncode == 0
    assert matching.stdout.strip() == "release tag v0.4.0 matches package version 0.4.0"
    assert unprefixed.returncode == 1
    assert mismatched.returncode == 1


def test_publish_workflow_builds_checked_out_release_tag_with_immutable_actions():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    triggers = workflow[True]
    assert triggers["push"] == {"tags": ["v*"]}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["tag"]["required"] is True
    assert set(workflow["jobs"]) == {"build", "github-release", "publish"}
    build = workflow["jobs"]["build"]
    github_release = workflow["jobs"]["github-release"]
    publish = workflow["jobs"]["publish"]
    assert build["permissions"] == {"contents": "read"}
    release_tag = "${{ inputs.tag || github.ref_name }}"
    assert build["env"] == {"RELEASE_TAG": release_tag}
    assert "environment" not in build
    assert github_release["needs"] == "build"
    assert github_release["permissions"] == {"contents": "write"}
    assert publish["needs"] == "github-release"
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"actions": "read", "id-token": "write"}
    steps = build["steps"]
    action_steps = [
        step
        for job in (build, github_release, publish)
        for step in job["steps"]
        if "uses" in step
    ]
    assert action_steps
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"]) for step in action_steps)
    checkout = next(step for step in action_steps if step["uses"].startswith("actions/checkout@"))
    assert checkout["uses"] == f"actions/checkout@{CHECKOUT_V7_SHA}"
    assert steps.index(checkout) < steps.index(verify := next(
        step for step in steps if step.get("name") == "Verify tag and documentation parity"
    ))
    assert checkout["with"] == {
        "ref": release_tag,
        "fetch-depth": 0,
        "persist-credentials": False,
    }
    assert "env" not in verify
    assert "scripts/verify_release_tag.py" in verify["run"]
    assert "scripts/sync-version-docs.py" in verify["run"]
    assert "--check" in verify["run"]
    assert "git rev-list -n 1" in verify["run"]
    assert "git merge-base --is-ancestor HEAD origin/main" in verify["run"]
    assert any(step.get("run") == "python -m build" for step in steps)
    assert any(step.get("run") == "python -m twine check --strict dist/*" for step in steps)

    uploads = [
        step for step in build["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 2
    assert {step["with"]["name"] for step in uploads} == {
        "release-distributions",
        "release-metadata",
    }
    assert all(step["uses"] == f"actions/upload-artifact@{UPLOAD_ARTIFACT_V7_SHA}" for step in uploads)
    assert all(step["with"]["overwrite"] is True for step in uploads)

    downloads = [
        step
        for job in (github_release, publish)
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert len(downloads) == 3
    assert all(download["uses"] == f"actions/download-artifact@{DOWNLOAD_ARTIFACT_V8_SHA}" for download in downloads)
    assert [download["with"]["name"] for download in downloads].count("release-distributions") == 2
    assert [download["with"]["name"] for download in downloads].count("release-metadata") == 1

    release_run = next(
        step["run"] for step in github_release["steps"] if step.get("name") == "Publish GitHub Release with curated notes"
    )
    assert "--notes-file dist/release-notes.md" in release_run
    assert "--generate-notes" not in release_run
    assert "--draft=false" in release_run
    assert "dist/*.whl dist/*.tar.gz" in release_run


def test_ci_workflow_uses_immutable_checkout_v7():
    workflow = yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))
    checkout_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 2
    assert all(step["uses"] == f"actions/checkout@{CHECKOUT_V7_SHA}" for step in checkout_steps)
