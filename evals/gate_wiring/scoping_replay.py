#!/usr/bin/env python3
"""Replay the frozen 972-finding development cohort after the 0.8.8 scope fix.

Labels and source files stay private. Explicit-file scans bypass directory scope;
report both modes without relabeling removed findings or changing gate parameters.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from replay import (
    FROZEN,
    LABELS,
    LOCAL,
    MANIFEST,
    ROOT,
    checked_map,
    detector_files,
    digest_tree,
    identity,
    model_files,
    read,
    sha,
    verify_manifest,
    write,
)


def summarize(rows: list[dict]) -> dict:
    buckets = defaultdict(Counter)
    rules = Counter()
    for row in rows:
        buckets[row["decision"]][row["label"]] += 1
        if row["decision"] == "KEEP" and row["label"] == "FP":
            rules[row["rule"]] += 1
    keep = buckets["KEEP"]
    visible = buckets["KEEP"] + buckets["ESCALATE"]
    return {
        "raw_findings": len(rows),
        "by_decision": {k: dict(v) for k, v in sorted(buckets.items())},
        "keep_precision_percent": 100 * keep["TP"] / (keep["TP"] + keep["FP"]),
        "visible_findings": sum(visible.values()),
        "visible_labels": dict(visible),
        "visible_false_positive_share_percent": 100 * visible["FP"] / (visible["TP"] + visible["FP"]),
        "keep_false_positives_by_rule": dict(sorted(rules.items())),
    }


def main() -> None:
    from lintlang.scanner import NON_PROMPT_DIRS, scan_file

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retired-h5", action="store_true", help="Measure the additional H5 retirement")
    args = parser.parse_args()
    retired_rules = {"H1.1", "H5"} if args.retired_h5 else {"H1.1"}
    manifest = read(MANIFEST)
    verify_manifest(manifest, read(FROZEN / "summary.json"))
    frozen = checked_map(read(FROZEN / "candidate-gated.json"), "frozen")
    labels = checked_map(read(LABELS), "labels")
    assert len(frozen) == 972 and frozen.keys() == labels.keys()
    model_before = digest_tree(model_files())
    assert model_before == read(ROOT / "evals/gate_wiring/results.json")["model_artifact_sha256"]
    source_before = digest_tree(detector_files())
    excluded_dirs = {
        "tests", "test", "cassettes", "fixtures", "mocks", "memory-tests",
        "examples", "cookbook", "tutorials", "lessons",
    }
    assert excluded_dirs <= NON_PROMPT_DIRS
    rows, removed = [], []
    current = set()
    for item in manifest["files"]:
        path = item["path"]
        # Both entrypoints run on the real frozen source, not saved finding text.
        raw = scan_file(path, gate=False)
        delivered = scan_file(path)
        assert not raw.input_error and not delivered.input_error and not delivered.gate_error
        assert delivered.gate_status == "evaluated"
        assert delivered.gate_thresholds == {"keep": 0.85, "dismiss": 0.15}
        assert delivered.raw_findings_count == len(raw.structural_findings)
        actual = {identity(path, f): f for f in delivered.structural_findings}
        raw_keys = {identity(path, f) for f in raw.structural_findings}
        assert len(raw_keys) == len(raw.structural_findings)
        assert actual.keys() == {k for k in raw_keys if frozen[k]["gate_decision"] != "DISMISS"}
        excluded = sorted(excluded_dirs.intersection(part.lower() for part in Path(path).parts[:-1]))
        for key in raw_keys:
            assert key in frozen and key not in current
            current.add(key)
            old, label = frozen[key], labels[key]
            if key in actual:
                assert actual[key].gate_decision == old["gate_decision"]
                assert actual[key].gate_probability == old["gate_probability"]
                assert actual[key].severity.value == old["severity"]
            row = {"finding_id": label["finding_id"], "rule": old["identity"][0],
                   "label": label["label"], "decision": old["gate_decision"],
                   "excluded_directories": excluded}
            assert row["label"] in {"TP", "FP", "UNRESOLVED"}
            rows.append(row)
        assert sha(Path(path).read_bytes()) == item["sha256"]
    for key in frozen.keys() - current:
        assert frozen[key]["identity"][0] in retired_rules, "Unexpected detector loss"
        removed.append({"finding_id": labels[key]["finding_id"], "label": labels[key]["label"], "rule": frozen[key]["identity"][0], "reason": "detector retired"})
    scoped = [row for row in rows if not row["excluded_directories"]]
    assert model_before == digest_tree(model_files())
    assert source_before == digest_tree(detector_files())
    summary = {
        "status": "PASS_REPLAY", "frozen_findings": 972, "verified_source_files": len(manifest["files"]),
        "manifest_sha256": sha(MANIFEST.read_bytes()), "labels_sha256": sha(LABELS.read_bytes()),
        "model_artifact_sha256": model_before, "detector_source_sha256": source_before,
        "thresholds": {"keep": 0.85, "dismiss": 0.15},
        "explicit_file_replay": summarize(rows), "directory_scoped_replay": summarize(scoped),
        "retired_labels_by_rule": {rule: dict(Counter(row["label"] for row in removed if row["rule"] == rule)) for rule in sorted(retired_rules)},
        "scope_removed_labels": dict(Counter(row["label"] for row in rows if row["excluded_directories"])),
        "scope_removed_findings": len(rows) - len(scoped),
        "boundary": "Frozen development cohort with mixed historical and AI-review labels; one unresolved finding. "
                    "Percentages use resolved TP+FP denominators. Visible means KEEP plus ESCALATE. "
                    "False-positive share is not FPR over negative inputs. Directory scope applies the ten new "
                    "component exclusions to the frozen file manifest; explicit-file scans remain available. "
                    "No labels, model weights, or thresholds changed. Only explicitly retired rules may disappear from explicit-file replay.",
    }
    write(LOCAL / ("h5-h18/per-finding.json" if args.retired_h5 else "scoping-fix/per-finding.json"), {"current": rows, "retired": removed})
    write(ROOT / "evals/gate_wiring" / ("h5-removal-results.json" if args.retired_h5 else "scoping-results.json"), summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
