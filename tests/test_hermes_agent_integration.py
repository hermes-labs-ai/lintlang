from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path

from lintlang.integrations.hermes_agent import _is_instruction_surface, pre_verify, register


class FakePluginContext:
    def __init__(self) -> None:
        self.hooks: list[tuple[str, object]] = []

    def register_hook(self, name: str, callback: object) -> None:
        self.hooks.append((name, callback))


def test_registers_documented_pre_verify_hook() -> None:
    ctx = FakePluginContext()
    register(ctx)
    assert ctx.hooks == [("pre_verify", pre_verify)]


def test_entry_point_loads_register_function() -> None:
    entry_point = EntryPoint(
        name="lintlang",
        value="lintlang.integrations.hermes_agent:register",
        group="hermes_agent.plugins",
    )
    assert entry_point.load() is register


def test_instruction_surface_scope_is_narrow() -> None:
    assert _is_instruction_surface(Path("AGENTS.md"))
    assert _is_instruction_surface(Path("plugins/weather/tools.py"))
    assert not _is_instruction_surface(Path("src/database.py"))
    assert not _is_instruction_surface(Path("README.md"))


def test_fail_keeps_one_coding_turn_open(tmp_path) -> None:
    prompt = tmp_path / "prompts" / "agent.yaml"
    prompt.parent.mkdir()
    prompt.write_text('tools:\n  - name: lookup\n    description: "Do stuff"\n', encoding="utf-8")

    result = pre_verify(coding=True, attempt=0, changed_paths=[str(prompt)])

    assert result is not None
    assert result["action"] == "continue"
    assert "lintlang scan" in result["message"]
    assert str(prompt) in result["message"]


def test_pass_review_non_coding_and_retry_do_not_nudge(tmp_path) -> None:
    prompt = tmp_path / "AGENTS.md"
    prompt.write_text(
        "You are a bounded assistant. Use the lookup tool only for current records. "
        "Stop after one attempt and report any missing record.",
        encoding="utf-8",
    )

    assert pre_verify(coding=True, attempt=0, changed_paths=[str(prompt)]) is None
    assert pre_verify(coding=False, attempt=0, changed_paths=[str(prompt)]) is None
    assert pre_verify(coding=True, attempt=1, changed_paths=[str(prompt)]) is None
