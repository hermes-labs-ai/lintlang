"""Hermes Gate lints changed production instructions, not release fixtures."""

import importlib.util
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / "scripts" / "lintlang_gate_targets.py"


def test_gate_target_selection_keeps_real_instructions_only(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("lintlang_gate_targets", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    names = [
        "AGENTS.md",
        "skills/release/SKILL.md",
        ".github/copilot-instructions.md",
        "prompts/system.prompt",
        "samples/release_088/AGENTS.md",
        "tests/fixtures/SKILL.md",
        "src/lintlang/patterns.py",
    ]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    assert module.select_targets(names) == sorted(names[:4])
