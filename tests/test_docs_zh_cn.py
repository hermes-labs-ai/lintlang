"""Guardrails for the Simplified-Chinese landing page.

`README.md` is canonical. The zh-CN page may only restate its commands, must not
hard-code a stale version, must link back to the English README, and must stay
short enough that it does not become a second README.
"""

from __future__ import annotations

import re
from pathlib import Path

import lintlang

REPO_ROOT = Path(__file__).resolve().parent.parent
ZH_DIR = REPO_ROOT / "docs" / "zh-CN"
ZH_README = ZH_DIR / "README.md"
CANONICAL = REPO_ROOT / "README.md"
MAX_LINES = 120

FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _blocks(text: str) -> list[str]:
    return [m.group(1).strip("\n") for m in FENCE.finditer(text)]


def test_zh_cn_readme_exists():
    assert ZH_README.is_file()


def test_zh_cn_code_blocks_are_verbatim_from_canonical_readme():
    canonical = _blocks(_text(CANONICAL))
    zh_blocks = _blocks(_text(ZH_README))
    assert zh_blocks, "zh-CN README should contain at least one command block"
    for block in zh_blocks:
        assert block in canonical, f"command block not in README.md:\n{block}"


def test_zh_cn_commands_are_not_invented():
    canonical = _text(CANONICAL)
    for block in _blocks(_text(ZH_README)):
        for line in block.splitlines():
            assert line.strip() in canonical, f"command line not in README.md: {line!r}"


def test_zh_cn_version_literals_match_package_version():
    text = _text(ZH_README)
    literals = set(re.findall(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.])", text))
    assert literals <= {lintlang.__version__}, literals


def test_zh_cn_links_to_canonical_english_readme():
    text = _text(ZH_README)
    assert "](../../README.md)" in text
    assert "权威" in text  # states that the English README is authoritative


def test_zh_cn_relative_links_resolve():
    for target in LINK.findall(_text(ZH_README)):
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = (ZH_DIR / target.split("#", 1)[0]).resolve()
        assert path.exists(), f"broken relative link: {target}"


def test_zh_cn_readme_stays_short():
    lines = _text(ZH_README).splitlines()
    assert len(lines) <= MAX_LINES, f"{len(lines)} lines; keep the page a landing doc"
