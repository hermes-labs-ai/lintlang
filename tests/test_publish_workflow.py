"""Release workflow and tag/package coherence contracts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish.yml"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_release_tag.py"
CHECKOUT_V7_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
UPLOAD_ARTIFACT_V4_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
DOWNLOAD_ARTIFACT_V4_SHA = "d3f86a106a0bac45b974a628896c90dbdf5c8093"


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
    assert set(workflow["jobs"]) == {"build", "publish"}
    build = workflow["jobs"]["build"]
    publish = workflow["jobs"]["publish"]
    assert build["permissions"] == {"contents": "read"}
    assert "environment" not in build
    assert publish["needs"] == "build"
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"id-token": "write"}
    steps = build["steps"]
    action_steps = [
        step
        for job in (build, publish)
        for step in job["steps"]
        if "uses" in step
    ]
    assert action_steps
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"]) for step in action_steps)
    checkout = next(step for step in action_steps if step["uses"].startswith("actions/checkout@"))
    assert checkout["uses"] == f"actions/checkout@{CHECKOUT_V7_SHA}"
    assert steps.index(checkout) < steps.index(verify := next(
        step for step in steps if step.get("name") == "Verify release tag and commit"
    ))
    assert steps.index(checkout) < steps.index(next(step for step in steps if step.get("name") == "Build package"))
    assert checkout["with"] == {
        "ref": "${{ github.event.release.tag_name }}",
        "fetch-depth": 0,
        "persist-credentials": False,
    }
    assert verify["env"] == {"RELEASE_TAG": "${{ github.event.release.tag_name }}"}
    assert "scripts/verify_release_tag.py" in verify["run"]
    assert "git rev-list -n 1" in verify["run"]
    assert any(step.get("run") == "python -m build" for step in steps)
    assert any(step.get("run") == "python -m twine check dist/*" for step in steps)

    upload = next(step for step in build["steps"] if step.get("uses", "").startswith("actions/upload-artifact@"))
    download = next(
        step for step in publish["steps"] if step.get("uses", "").startswith("actions/download-artifact@")
    )
    assert upload["uses"] == f"actions/upload-artifact@{UPLOAD_ARTIFACT_V4_SHA}"
    assert upload["with"] == {
        "name": "release-distributions",
        "path": "dist/",
        "if-no-files-found": "error",
    }
    assert download["uses"] == f"actions/download-artifact@{DOWNLOAD_ARTIFACT_V4_SHA}"
    assert download["with"] == {
        "name": "release-distributions",
        "path": "dist/",
    }
