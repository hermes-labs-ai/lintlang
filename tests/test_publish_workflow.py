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
    publish = workflow["jobs"]["publish"]
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}
    steps = publish["steps"]
    action_steps = [step for step in steps if "uses" in step]
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
