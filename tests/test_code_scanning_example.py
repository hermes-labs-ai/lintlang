"""Contract tests for the documented GitHub Code Scanning workflow."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PATH = REPO_ROOT / "examples" / "github-code-scanning.yml"
UPLOAD_SARIF_V4_SHA = "5595ccaf912efad79be6eef63a5619ff05969be3"
FORK_SAFE_UPLOAD_CONDITION = (
    "always() && (github.event_name == 'push' || "
    "(github.actor != 'dependabot[bot]' && "
    "github.event.pull_request.head.repo.full_name == github.repository))"
)


def test_code_scanning_example_is_least_privilege_and_uploads_even_after_failure():
    text = EXAMPLE_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    assert "pull_request" in workflow[True]
    assert "pull_request_target" not in text
    assert workflow["permissions"] == {
        "contents": "read",
        "security-events": "write",
    }
    [job] = workflow["jobs"].values()
    steps = job["steps"]
    lintlang_step = next(step for step in steps if step.get("name") == "Run LintLang")
    upload_step = next(step for step in steps if step.get("name") == "Upload LintLang SARIF")
    assert lintlang_step["with"]["sarif-file"] == "lintlang.sarif"
    assert lintlang_step["with"]["fail-on"] == "fail"
    assert upload_step["if"] == FORK_SAFE_UPLOAD_CONDITION
    assert upload_step["with"]["sarif_file"] == "lintlang.sarif"
    assert upload_step["uses"] == f"github/codeql-action/upload-sarif@{UPLOAD_SARIF_V4_SHA}"
    assert re.search(
        rf"github/codeql-action/upload-sarif@{UPLOAD_SARIF_V4_SHA}\s+# v4\b",
        text,
    )


def test_readme_code_scanning_example_uses_the_same_fork_safe_upload_guard():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert f"if: {FORK_SAFE_UPLOAD_CONDITION}" in readme
    assert "pull_request_target" not in readme
