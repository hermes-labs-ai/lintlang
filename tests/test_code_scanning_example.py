"""Contract tests for the documented GitHub Code Scanning workflow."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PATH = REPO_ROOT / "examples" / "github-code-scanning.yml"
LINTLANG_V070_SHA = "175a9a19414aff9a1752d3b9850d6cf58d59fb32"
UPLOAD_ARTIFACT_V7_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD_ARTIFACT_V8_SHA = "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"
UPLOAD_SARIF_V4_SHA = "5595ccaf912efad79be6eef63a5619ff05969be3"
FORK_SAFE_UPLOAD_CONDITION = (
    "always() && (github.event_name == 'push' || "
    "(github.actor != 'dependabot[bot]' && "
    "github.event.pull_request.head.repo.full_name == github.repository))"
)


def test_code_scanning_example_is_least_privilege_and_uploads_even_after_failure():
    text = EXAMPLE_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    # PyYAML applies YAML 1.1 resolution, so the bare `on` key becomes True.
    assert "pull_request" in workflow[True]
    assert "push" in workflow[True]
    assert "pull_request_target" not in text
    assert "permissions" not in workflow
    assert set(workflow["jobs"]) == {"scan", "upload-sarif"}

    scan = workflow["jobs"]["scan"]
    upload = workflow["jobs"]["upload-sarif"]
    assert scan["permissions"] == {"contents": "read"}
    assert upload["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }
    assert upload["needs"] == "scan"
    assert upload["if"] == FORK_SAFE_UPLOAD_CONDITION

    checkout_step = next(step for step in scan["steps"] if step.get("name") == "Check out repository")
    lintlang_step = next(step for step in scan["steps"] if step.get("name") == "Run LintLang")
    preserve_step = next(step for step in scan["steps"] if step.get("name") == "Preserve LintLang SARIF")
    upload_checkout_step = next(
        step for step in upload["steps"] if step.get("name") == "Check out repository for SARIF fingerprinting"
    )
    download_step = next(step for step in upload["steps"] if step.get("name") == "Download LintLang SARIF")
    upload_step = next(step for step in upload["steps"] if step.get("name") == "Upload LintLang SARIF")
    assert checkout_step["with"]["persist-credentials"] is False
    assert lintlang_step["uses"] == f"hermes-labs-ai/lintlang@{LINTLANG_V070_SHA}"
    assert lintlang_step["with"]["path"] == "AGENTS.md"
    assert lintlang_step["with"]["sarif-file"] == "lintlang.sarif"
    assert lintlang_step["with"]["fail-on"] == "fail"
    assert "continue-on-error" not in lintlang_step
    assert preserve_step["if"] == "always()"
    assert preserve_step["uses"] == f"actions/upload-artifact@{UPLOAD_ARTIFACT_V7_SHA}"
    assert preserve_step["with"]["if-no-files-found"] == "error"
    assert upload_checkout_step["with"]["persist-credentials"] is False
    assert download_step["uses"] == f"actions/download-artifact@{DOWNLOAD_ARTIFACT_V8_SHA}"
    assert download_step["with"]["name"] == preserve_step["with"]["name"]
    assert upload_step["with"]["sarif_file"] == "lintlang.sarif"
    assert upload_step["uses"] == f"github/codeql-action/upload-sarif@{UPLOAD_SARIF_V4_SHA}"
    assert f"lintlang@{LINTLANG_V070_SHA} # v0.7.0" in text
    assert re.search(
        rf"github/codeql-action/upload-sarif@{UPLOAD_SARIF_V4_SHA}\s+# v4\b",
        text,
    )


def test_github_guide_routes_to_the_single_complete_workflow():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (REPO_ROOT / "docs/github.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "llms-full.txt").read_text(encoding="utf-8")
    assert "(docs/github.md)" in readme
    assert "## Code scanning\n" in guide
    assert "(../examples/github-code-scanning.yml)" in guide
    assert "(../action.yml)" in guide
    assert "(docs/github.md#code-scanning)" in reference
    # The full example above still enforces every pin, permission, and artifact
    # contract. Navigation replaces only the obsolete duplicated README YAML.
    for document in (readme, guide, reference):
        for block in re.findall(r"```yaml\n(.*?)\n```", document, flags=re.DOTALL):
            parsed = yaml.safe_load(block)
            assert not (isinstance(parsed, dict) and "jobs" in parsed), "Duplicate full workflow"
    assert "pull_request_target" not in readme
