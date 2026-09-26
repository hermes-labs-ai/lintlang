from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_opencode_adapter_is_bounded():
    plugin = (ROOT / "integrations/opencode/lintlang.js").read_text()
    assert '"tool.execute.after"' in plugin
    assert "MAX_FINDINGS = 8" in plugin


def test_opencode_adapter_reports_input_error_before_skipped_metadata():
    plugin = (ROOT / "integrations/opencode/lintlang.js").read_text()

    assert plugin.index("if (result.input_error)") < plugin.index("if (result.skipped)")
