"""Hermes Agent verification hook for changed instruction surfaces.

Hermes Agent discovers this module through its documented
``hermes_agent.plugins`` entry-point group. The hook is deliberately narrow:
it runs once, at Hermes' bounded ``pre_verify`` gate, and only for changed
files whose names or locations identify them as agent instructions, prompts,
skills, tools, or agent configuration. REVIEW findings remain advisory;
only FAIL or ERROR keeps the coding turn open.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lintlang import compute_verdict, scan_file

_EXACT_NAMES = {
    ".cursorrules",
    ".hermes.md",
    "agents.md",
    "claude.md",
    "copilot-instructions.md",
    "skill.md",
    "system.md",
    "system.prompt",
}
_LANGUAGE_SUFFIXES = {".json", ".md", ".prompt", ".py", ".txt", ".yaml", ".yml"}
_PATH_MARKERS = {"agent", "agents", "plugin", "plugins", "prompt", "prompts", "skill", "skills", "tool", "tools"}
_STEM_MARKERS = ("agent", "instruction", "plugin", "prompt", "skill", "system", "tool")


def _is_instruction_surface(path: Path) -> bool:
    """Return whether a changed path is a plausible LintLang input."""
    if path.name.lower() in _EXACT_NAMES:
        return True
    if path.suffix.lower() not in _LANGUAGE_SUFFIXES:
        return False
    lowered_parts = {part.lower() for part in path.parts}
    return bool(lowered_parts & _PATH_MARKERS) or any(marker in path.stem.lower() for marker in _STEM_MARKERS)


def _blocking_summary(paths: Iterable[str]) -> list[str]:
    """Scan existing eligible files and return concise FAIL/ERROR summaries."""
    blocked: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file() or not _is_instruction_surface(path):
            continue
        result = scan_file(path)
        verdict = compute_verdict(result)
        if verdict not in {"FAIL", "ERROR"}:
            continue
        detail = result.input_error
        if not detail and result.structural_findings:
            finding = result.structural_findings[0]
            detail = f"{finding.code} {finding.description}"
        blocked.append(f"{path}: {verdict}" + (f" — {detail}" if detail else ""))
    return blocked


def pre_verify(*, coding: bool, attempt: int, changed_paths: list[str], **_: Any) -> dict[str, str] | None:
    """Keep one Hermes coding turn open when changed agent language fails lint."""
    if not coding or attempt:
        return None
    blocked = _blocking_summary(changed_paths)
    if not blocked:
        return None
    lines = "\n".join(f"- {line}" for line in blocked[:5])
    suffix = "\n- additional changed inputs omitted" if len(blocked) > 5 else ""
    return {
        "action": "continue",
        "message": (
            "LintLang found a blocking issue in changed agent-language files:\n"
            f"{lines}{suffix}\n"
            "Run `lintlang scan <path> --fail-on fail`, repair or explicitly exclude the input, "
            "then verify again. A clean scan is structural evidence only, not a runtime-safety claim."
        ),
    }


def register(ctx: Any) -> None:
    """Register the bounded verification hook with Hermes Agent."""
    ctx.register_hook("pre_verify", pre_verify)
