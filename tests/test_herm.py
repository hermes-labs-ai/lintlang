"""Focused regressions for HERM signal detection."""

import json
from pathlib import Path

from lintlang.herm import score_text
from lintlang.scanner import scan_file

ROOT = Path(__file__).parent.parent
CORPUS_PATH = ROOT / "evals" / "corpus" / "cases.jsonl"
SAMPLES_DIR = ROOT / "samples"


def _load_case(case_id: str) -> dict:
    cases = [json.loads(line) for line in CORPUS_PATH.read_text().splitlines() if line.strip()]
    return next(case for case in cases if case["case_id"] == case_id)


def test_priority_order_prose_corpus_boundary() -> None:
    case = _load_case("LL-HERM-PRIORITY-001")

    for variant in case["variants"]:
        result = score_text(variant["text"], source_path=variant["source_path"])
        expected = variant["expect"]

        assert result.signal_counts["priority"] == expected["signal_counts"]["priority"], variant["variant_id"]
        for finding in expected.get("findings_absent", []):
            assert finding not in result.findings, variant["variant_id"]
        for finding in expected.get("findings_present", []):
            assert finding in result.findings, variant["variant_id"]


def test_priority_order_prose_scanner_fixture() -> None:
    result = scan_file(SAMPLES_DIR / "herm_priority_ordering.yaml")

    assert result.input_error is None
    assert result.herm.signal_counts["priority"] == 1
    assert "No explicit priority ordering" not in result.herm.findings
