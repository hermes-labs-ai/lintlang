#!/usr/bin/env python3
"""Replay the current private candidate against all 972 frozen finding labels.

Preserve historical receipts. Only H5 retirement, H1.8 language scope, and
recognized H1.8 triggers may remove identities from the original snapshot.
"""

from __future__ import annotations

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

from lintlang import __version__
from lintlang.detectors.h1 import _SKILL_TRIGGER
from lintlang.detectors.lang import H18_LANGUAGES, detect, normalize
from lintlang.parsers import parse_source, read_file_text
from lintlang.scanner import scan_file


def summarize(rows: list[dict]) -> dict:
    buckets = defaultdict(Counter)
    rules = Counter()
    for row in rows:
        buckets[row["decision"]][row["label"]] += 1
        if row["decision"] == "KEEP" and row["label"] == "FP":
            rules[row["rule"]] += 1
    keep = buckets["KEEP"]
    visible = keep + buckets["ESCALATE"]
    keep_resolved = keep["TP"] + keep["FP"]
    visible_resolved = visible["TP"] + visible["FP"]
    return {"raw_findings": len(rows),
            "by_decision": {key: dict(value) for key, value in sorted(buckets.items())},
            "keep_precision_percent": 100 * keep["TP"] / keep_resolved if keep_resolved else None,
            "visible_findings": sum(visible.values()), "visible_labels": dict(visible),
            "visible_false_positive_share_percent": (
                100 * visible["FP"] / visible_resolved if visible_resolved else None),
            "keep_false_positives_by_rule": dict(sorted(rules.items()))}


def removal_reason(row: dict) -> str:
    rule = row["identity"][0]
    if rule == "H5":
        return "H5 retired"
    if rule != "H1.8":
        raise ValueError(f"Unexpected removed rule: {rule}")
    path = Path(row["path"])
    skill = parse_source(read_file_text(path), path).skill
    if skill is None:
        raise ValueError("Removed H1.8 source no longer parses")
    language = detect(skill.description.strip())
    if language not in H18_LANGUAGES:
        return "H1.8 language excluded"
    if row["label"] == "TP":
        raise ValueError("An eligible CJK H1.8 TP was removed")
    if not _SKILL_TRIGGER.search(normalize(skill.description.strip())):
        raise ValueError("Removed H1.8 has no recognized trigger")
    return "H1.8 trigger recognized"


def main() -> None:
    manifest = read(MANIFEST)
    verify_manifest(manifest, read(FROZEN / "summary.json"))
    frozen = checked_map(read(FROZEN / "candidate-gated.json"), "frozen")
    labels = checked_map(read(LABELS), "labels")
    if len(frozen) != 972 or frozen.keys() != labels.keys():
        raise ValueError("Expected exactly 972 frozen labeled identities")
    model_before = digest_tree(model_files())
    if model_before != read(ROOT / "evals/gate_wiring/results.json")["model_artifact_sha256"]:
        raise ValueError("Gate artifacts changed from the historical receipt")
    source_before = digest_tree(detector_files())
    current, rows, removed = set(), [], []
    for item in manifest["files"]:
        path = item["path"]
        raw, delivered = scan_file(path, gate=False), scan_file(path)
        if raw.input_error or delivered.input_error or delivered.gate_error:
            raise ValueError("Corpus scan or default gate unavailable")
        if delivered.gate_status != "evaluated" or delivered.gate_thresholds != {"keep": 0.85, "dismiss": 0.15}:
            raise ValueError("Default gate policy changed")
        raw_keys = {identity(path, finding) for finding in raw.structural_findings}
        if len(raw_keys) != len(raw.structural_findings) or not raw_keys <= frozen.keys():
            raise ValueError("Duplicate or unlabeled current finding")
        actual = {identity(path, finding): finding for finding in delivered.structural_findings}
        if actual.keys() != {key for key in raw_keys if frozen[key]["gate_decision"] != "DISMISS"}:
            raise ValueError("Actual default delivery differs from frozen decisions")
        if (delivered.raw_findings_count != len(raw_keys)
                or delivered.suppressed_count != len(raw_keys) - len(actual)):
            raise ValueError("Default gate count mismatch")
        for key in raw_keys:
            if key in current:
                raise ValueError("Duplicate corpus finding identity")
            current.add(key)
            old, label = frozen[key], labels[key]
            if key in actual:
                finding = actual[key]
                if (finding.gate_decision != old["gate_decision"]
                        or finding.gate_probability != old["gate_probability"]
                        or finding.severity.value != old["severity"]):
                    raise ValueError("Actual delivered score, decision, or severity changed")
            rows.append({"finding_id": label["finding_id"], "rule": old["identity"][0],
                         "label": label["label"], "decision": old["gate_decision"]})
        if sha(Path(path).read_bytes()) != item["sha256"]:
            raise ValueError("Corpus source changed during replay")
    for key in frozen.keys() - current:
        label = labels[key]
        removed.append({"finding_id": label["finding_id"], "label": label["label"],
                        "rule": label["identity"][0], "reason": removal_reason(label)})
    if model_before != digest_tree(model_files()) or source_before != digest_tree(detector_files()):
        raise ValueError("Source or model changed during replay")
    by_rule = defaultdict(list)
    for row in rows:
        by_rule[row["rule"]].append(row)
    h18 = read(ROOT / "evals/gate_wiring/h18-language-results.json")
    expected_tps = h18["all_h18_tp_audit"]["counts"]["all"]["tp_before"]
    if sum(row["label"] == "TP" for row in by_rule["H1.8"]) != expected_tps or expected_tps != 249:
        raise ValueError("The full replay did not retain all 249 eligible H1.8 TPs")
    result = {"status": "PASS_REPLAY", "version": __version__, "frozen_findings": 972,
              "verified_source_files": len(manifest["files"]), "manifest_sha256": sha(MANIFEST.read_bytes()),
              "labels_sha256": sha(LABELS.read_bytes()), "model_artifact_sha256": model_before,
              "detector_source_sha256": source_before, "thresholds": {"keep": 0.85, "dismiss": 0.15},
              "current": summarize(rows), "by_rule": {rule: summarize(records) for rule, records in by_rule.items()},
              "removed": {reason: dict(Counter(row["label"] for row in removed if row["reason"] == reason))
                          for reason in sorted({row["reason"] for row in removed})},
              "h18_all_tp_retained": expected_tps, "h18_keep_counts": h18["counts"]["all"],
              "boundary": "Frozen development replay with mixed historical and AI-review labels. "
                          "KEEP precision uses resolved TP+FP labels; this is not held-out population accuracy. "
                          "Default scanner delivery, scores, identities, and unchanged gate artifacts checked. "
                          "Excluded language records are not counted as FP or TP. Historical receipts are preserved."}
    if sum(summary["raw_findings"] for summary in result["by_rule"].values()) != result["current"]["raw_findings"]:
        raise ValueError("Rule breakdown does not reconcile with the raw finding total")
    write(LOCAL / "release-090-current/per-finding.json", {"current": rows, "removed": removed})
    write(ROOT / "evals/gate_wiring/current-results.json", result)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
