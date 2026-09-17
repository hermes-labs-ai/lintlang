"""Security contracts for the repository CI workflow."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = yaml.safe_load(
    (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
)
LINTLANG_WORKFLOW = yaml.safe_load(
    (REPO_ROOT / ".github" / "workflows" / "lintlang.yml").read_text(encoding="utf-8")
)

REUSABLE_LINTLANG_WORKFLOW_SHA = "24f689992794ea08d905419f1e94a0274ba99ae4"


def test_ci_checkout_credentials_are_not_available_to_repository_code():
    checkout_steps = [
        step
        for job in CI_WORKFLOW["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 2
    assert all(step.get("with", {}).get("persist-credentials") is False for step in checkout_steps)


def test_lintlang_reusable_workflow_is_pinned_and_keeps_sarif_permission():
    job = LINTLANG_WORKFLOW["jobs"]["language-contract"]

    assert job["uses"] == (
        "hermes-labs-ai/.github/.github/workflows/reusable-lintlang.yml@"
        f"{REUSABLE_LINTLANG_WORKFLOW_SHA}"
    )
    assert LINTLANG_WORKFLOW["permissions"] == {
        "contents": "read",
        "security-events": "write",
    }
