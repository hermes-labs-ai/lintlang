"""Security contracts for the OpenSSF Scorecard workflow."""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "scorecard.yml"
SCORECARD_WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

FULL_SHA = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def _steps():
    return [step for job in SCORECARD_WORKFLOW["jobs"].values() for step in job["steps"]]


def test_scorecard_checkout_credentials_are_not_persisted():
    checkout_steps = [step for step in _steps() if step.get("uses", "").startswith("actions/checkout@")]

    assert checkout_steps
    assert all(step.get("with", {}).get("persist-credentials") is False for step in checkout_steps)


def test_scorecard_default_permissions_are_read_only():
    assert SCORECARD_WORKFLOW["permissions"] == "read-all"


def test_scorecard_job_grants_only_the_scopes_it_needs():
    job_permissions = SCORECARD_WORKFLOW["jobs"]["analysis"]["permissions"]

    assert job_permissions == {"security-events": "write", "id-token": "write"}


def test_scorecard_actions_are_pinned_to_full_length_commit_shas():
    pinned = [step["uses"] for step in _steps() if "uses" in step]

    assert pinned
    assert all(FULL_SHA.match(ref) for ref in pinned)


def test_scorecard_runs_on_the_default_branch_and_its_schedule():
    on = SCORECARD_WORKFLOW[True] if True in SCORECARD_WORKFLOW else SCORECARD_WORKFLOW["on"]

    assert on["push"]["branches"] == ["main"]
    assert "schedule" in on
    assert "branch_protection_rule" in on
