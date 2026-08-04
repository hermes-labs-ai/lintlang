"""Contract tests for the first-party composite GitHub Action."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION = yaml.safe_load((REPO_ROOT / "action.yml").read_text(encoding="utf-8"))


def test_marketplace_metadata_and_inputs_are_minimal():
    assert ACTION["name"] == "LintLang Agent Config Linter"
    assert ACTION["description"]
    assert ACTION["branding"] == {"icon": "check-circle", "color": "blue"}
    assert ACTION["runs"]["using"] == "composite"
    assert ACTION.get("outputs") is None

    inputs = ACTION["inputs"]
    assert set(inputs) == {"path", "fail-on", "python-version"}
    assert inputs["path"]["required"] is True
    assert inputs["fail-on"]["default"] == "fail"
    assert inputs["python-version"]["default"] == "3.12"


def test_setup_python_is_pinned_to_a_full_commit_sha():
    setup = ACTION["runs"]["steps"][0]
    owner_repo, sha = setup["uses"].split("@", maxsplit=1)
    assert owner_repo == "actions/setup-python"
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert setup["with"]["python-version"] == "${{ inputs.python-version }}"


def test_selected_action_ref_is_installed_and_inputs_are_not_shell_interpolated():
    install, scan = ACTION["runs"]["steps"][1:]
    assert install["run"] == 'python -m pip install "$GITHUB_ACTION_PATH"'
    assert scan["env"] == {
        "LINTLANG_PATH": "${{ inputs.path }}",
        "LINTLANG_FAIL_ON": "${{ inputs.fail-on }}",
    }
    assert scan["run"] == 'lintlang scan "$LINTLANG_PATH" --fail-on "$LINTLANG_FAIL_ON"'
    assert "${{" not in install["run"]
    assert "${{" not in scan["run"]
