"""Keep release integration defaults aligned with published artifacts."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ACTION_SHA = "645f57879ff5dbe3bbff37e9696834fb00371194"
# Reviewed consumer release, independent of unreleased source version bumps.
PACKAGE_VERSION = "0.8.3"


def test_release_integration_defaults_do_not_regress():
    feature = json.loads(
        (ROOT / "integrations/devcontainer/src/lintlang/devcontainer-feature.json").read_text()
    )
    installer = (ROOT / "integrations/devcontainer/src/lintlang/install.sh").read_text()
    initializer = (ROOT / "src/lintlang/github_init.py").read_text()
    example = (ROOT / "examples/github-code-scanning.yml").read_text()

    assert feature["version"] == "1.0.1"
    assert feature["options"]["version"]["default"] == PACKAGE_VERSION
    assert f"VERSION:-{PACKAGE_VERSION}" in installer
    for workflow in (initializer, example):
        assert f"hermes-labs-ai/lintlang@{ACTION_SHA} # v{PACKAGE_VERSION}" in workflow
        assert "hermes-labs-ai/lintlang@58e66871531eb585869336189d07b4334e963a5f" not in workflow


def test_released_action_ci_exercises_the_recommended_pin_and_explicit_gate():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["action-smoke"]["steps"]
    released = [step for step in steps if step.get("name", "").startswith("Released Action")]
    assert len(released) == 2
    assert {step["uses"] for step in released} == {f"hermes-labs-ai/lintlang@{ACTION_SHA}"}
    failing = next(step for step in released if step.get("id") == "released-failing-scan")
    assert failing["with"]["fail-on"] == "fail"
    verification = next(step for step in steps if step.get("name", "").startswith("Assert released Action"))
    assert verification["env"]["EXPECTED_LINTLANG_VERSION"] == PACKAGE_VERSION
    assert 'os.environ["EXPECTED_LINTLANG_VERSION"]' in verification["run"]
    assert 'version("lintlang")' not in verification["run"]


def test_feature_documentation_and_native_scenario_follow_the_default():
    feature = ROOT / "integrations/devcontainer"
    readme = (feature / "src/lintlang/README.md").read_text()
    scenario = (feature / "test/lintlang/test.sh").read_text()
    assert f"The default package pin is LintLang `{PACKAGE_VERSION}`" in readme
    assert f'"version": "{PACKAGE_VERSION}"' in readme
    assert f"lintlang {PACKAGE_VERSION}" in scenario
