"""Contract tests for the first-party composite GitHub Action."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION = yaml.safe_load((REPO_ROOT / "action.yml").read_text(encoding="utf-8"))


def _real_lintlang_path(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    command = fake_bin / "lintlang"
    command.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" -m lintlang "$@"\n', encoding="utf-8")
    command.chmod(0o755)
    return fake_bin


def test_marketplace_metadata_and_inputs_are_minimal():
    assert ACTION["name"] == "LintLang Agent Config Linter"
    assert ACTION["description"]
    assert ACTION["branding"] == {"icon": "check-circle", "color": "blue"}
    assert ACTION["runs"]["using"] == "composite"
    assert ACTION.get("outputs") is None

    inputs = ACTION["inputs"]
    assert set(inputs) == {"path", "fail-on", "python-version", "sarif-file"}
    assert inputs["path"]["required"] is True
    assert inputs["fail-on"]["default"] == "fail"
    assert inputs["python-version"]["default"] == "3.12"
    assert inputs["sarif-file"]["required"] is False
    assert inputs["sarif-file"]["default"] == ""


def test_setup_python_is_pinned_to_a_full_commit_sha():
    setup = ACTION["runs"]["steps"][0]
    owner_repo, sha = setup["uses"].split("@", maxsplit=1)
    assert owner_repo == "actions/setup-python"
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert setup["with"]["python-version"] == "${{ inputs.python-version }}"


def test_selected_action_ref_is_installed_and_inputs_are_not_shell_interpolated():
    install, scan, sarif_scan = ACTION["runs"]["steps"][1:]
    assert install["run"] == 'python -m pip install "$GITHUB_ACTION_PATH"'
    assert scan["if"] == "inputs.sarif-file == ''"
    assert scan["env"] == {
        "LINTLANG_PATH": "${{ inputs.path }}",
        "LINTLANG_FAIL_ON": "${{ inputs.fail-on }}",
    }
    assert scan["run"] == 'lintlang scan "$LINTLANG_PATH" --fail-on "$LINTLANG_FAIL_ON"'
    assert sarif_scan["if"] == "inputs.sarif-file != ''"
    assert sarif_scan["env"] == {
        "LINTLANG_PATH": "${{ inputs.path }}",
        "LINTLANG_FAIL_ON": "${{ inputs.fail-on }}",
        "LINTLANG_SARIF_FILE": "${{ inputs.sarif-file }}",
    }
    assert "${{" not in install["run"]
    assert "${{" not in scan["run"]
    assert "${{" not in sarif_scan["run"]


def test_default_action_command_preserves_clean_and_failing_fixtures(tmp_path):
    lintlang_bin = _real_lintlang_path(tmp_path)
    scan = ACTION["runs"]["steps"][2]
    base_env = {
        **os.environ,
        "PATH": f"{lintlang_bin}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "LINTLANG_FAIL_ON": "fail",
    }

    outcomes = []
    for fixture in ("clean_config.yaml", "bad_tool_descriptions.yaml"):
        completed = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", scan["run"]],
            cwd=REPO_ROOT,
            env={**base_env, "LINTLANG_PATH": f"samples/{fixture}"},
            text=True,
            capture_output=True,
            check=False,
        )
        outcomes.append(completed.returncode)

    assert outcomes == [0, 1]


def test_sarif_step_writes_real_report_before_preserving_failing_verdict(tmp_path):
    lintlang_bin = _real_lintlang_path(tmp_path)
    report = tmp_path / "nested" / "lintlang.sarif"
    sarif_scan = ACTION["runs"]["steps"][3]
    env = {
        **os.environ,
        "PATH": f"{lintlang_bin}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "LINTLANG_PATH": "samples/bad_tool_descriptions.yaml",
        "LINTLANG_FAIL_ON": "fail",
        "LINTLANG_SARIF_FILE": str(report),
    }

    completed = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", sarif_scan["run"]],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    document = json.loads(report.read_text(encoding="utf-8"))
    assert document["version"] == "2.1.0"
    assert document["runs"][0]["results"]


def test_sarif_step_rejects_output_that_is_the_input_without_overwriting_it(tmp_path):
    lintlang_bin = _real_lintlang_path(tmp_path)
    source = tmp_path / "agent.yaml"
    original = "system_prompt: Be concise.\n"
    source.write_text(original, encoding="utf-8")
    sarif_scan = ACTION["runs"]["steps"][3]
    env = {
        **os.environ,
        "PATH": f"{lintlang_bin}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "LINTLANG_PATH": str(source),
        "LINTLANG_FAIL_ON": "fail",
        "LINTLANG_SARIF_FILE": str(source),
    }

    completed = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", sarif_scan["run"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert source.read_text(encoding="utf-8") == original
    assert "must differ" in completed.stderr


def test_sarif_step_does_not_add_its_output_to_a_directory_scan(tmp_path):
    lintlang_bin = _real_lintlang_path(tmp_path)
    scan_root = tmp_path / "configs"
    scan_root.mkdir()
    (scan_root / "agent.yaml").write_text("system_prompt: Be concise.\n", encoding="utf-8")
    report = scan_root / "lintlang.sarif.json"
    sarif_scan = ACTION["runs"]["steps"][3]
    env = {
        **os.environ,
        "PATH": f"{lintlang_bin}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "LINTLANG_PATH": str(scan_root),
        "LINTLANG_FAIL_ON": "fail",
        "LINTLANG_SARIF_FILE": str(report),
    }

    completed = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", sarif_scan["run"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    document = json.loads(report.read_text(encoding="utf-8"))
    assert document["runs"][0]["invocations"][0]["executionSuccessful"] is True
