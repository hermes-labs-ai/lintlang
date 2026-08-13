"""Security contracts for the repository CI workflow."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = yaml.safe_load(
    (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
)


def test_ci_checkout_credentials_are_not_available_to_repository_code():
    checkout_steps = [
        step
        for job in CI_WORKFLOW["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 2
    assert all(step.get("with", {}).get("persist-credentials") is False for step in checkout_steps)
