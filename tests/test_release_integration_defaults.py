"""Keep release integration defaults aligned with published artifacts."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTION_SHA = "175a9a19414aff9a1752d3b9850d6cf58d59fb32"
PACKAGE_VERSION = "0.7.0"


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
        assert f"hermes-labs-ai/lintlang@{ACTION_SHA} # v0.7.0" in workflow
        assert "hermes-labs-ai/lintlang@58e66871531eb585869336189d07b4334e963a5f" not in workflow
