from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_opencode_adapter_is_bounded_and_documents_contract():
    plugin = (ROOT / "integrations/opencode/lintlang.js").read_text()
    docs = (ROOT / "integrations/opencode/README.md").read_text()
    assert '"tool.execute.after"' in plugin
    assert "MAX_FINDINGS = 8" in plugin
    assert "file.edited" in docs
    assert "explicit path" in docs
    assert "raw" in docs and "evidence" in docs
