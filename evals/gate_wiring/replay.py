#!/usr/bin/env python3
"""Replay the frozen 0.8.8 corpus through the current default gate.

The corpus manifest, finding identities, labels, and per-file records stay under
``.hermes/local``.  The public result contains aggregates and digests only.
No detector, model, threshold, or label is changed by this runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".hermes/local"
MANIFEST = LOCAL / "release-088-eval/manifest.json"
FROZEN = LOCAL / "release-088-eval/final"
LABELS = LOCAL / "release-088-labeling/all-labeled-findings.json"
PRIVATE = LOCAL / "gate-wiring-eval"
PUBLIC = ROOT / "evals/gate_wiring/results.json"
ARTIFACTS = ROOT / "src/lintlang/gate/artifacts"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def identity(path: str, finding) -> tuple:
    if isinstance(finding, dict):
        return (path, *finding["identity"])
    return (path, finding.code, finding.location,
            finding.source_region.start_line if finding.source_region else None,
            finding.description, finding.evidence)


def digest_tree(paths: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}


def model_files() -> list[Path]:
    return [ARTIFACTS / name for name in ("model.json", "scaler.json", "thresholds.json")]


def detector_files() -> list[Path]:
    return sorted((ROOT / "src/lintlang/detectors").rglob("*.py")) + [
        ROOT / "src/lintlang/patterns.py", ROOT / "src/lintlang/scanner.py",
        ROOT / "src/lintlang/parsers.py", ROOT / "src/lintlang/extractors.py",
    ]


def verify_manifest(manifest: dict, frozen_summary: dict) -> None:
    if len(manifest["files"]) != 1599:
        raise ValueError("Frozen corpus is not the expected 1,599 files")
    if sha(MANIFEST.read_bytes()) != frozen_summary["manifest_sha256"]:
        raise ValueError("Manifest differs from the frozen candidate receipt")
    paths = [row["path"] for row in manifest["files"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate corpus path")
    for item in manifest["files"]:
        if sha(Path(item["path"]).read_bytes()) != item["sha256"]:
            raise ValueError("Corpus source hash changed")


def checked_map(rows: list[dict], name: str) -> dict[tuple, dict]:
    result = {}
    for row in rows:
        key = identity(row["path"], row)
        if key in result:
            raise ValueError(f"Duplicate {name} finding identity")
        result[key] = row
    return result


def choose_probes(frozen_gated: list[dict]) -> list[str]:
    by_file: dict[str, set[str]] = defaultdict(set)
    for row in frozen_gated:
        by_file[row["path"]].add(row["gate_decision"])
    keep_dismiss = sorted(path for path, decisions in by_file.items()
                          if {"KEEP", "DISMISS"} <= decisions)
    escalate_only = sorted(path for path, decisions in by_file.items()
                           if decisions == {"ESCALATE"})
    if not keep_dismiss or not escalate_only:
        raise ValueError("No representative CLI probe files")
    return [keep_dismiss[0], escalate_only[0]]


def cli_probes(paths: list[str], delivered_by_file: dict[str, list],
               raw_counts: dict[str, int], verdicts: dict[str, str]) -> dict:
    """Check each format on two representative files, never shelling over the corpus."""
    probe_rows = []
    for path in paths:
        file_rows = []
        expected_count = len(delivered_by_file[path])
        expected_raw = raw_counts[path]
        expected_exit = int(verdicts[path] == "FAIL")
        for fmt in ("json", "sarif", "gitlab"):
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            proc = subprocess.run(
                [sys.executable, "-m", "lintlang", "scan", path, "--format", fmt],
                cwd=Path(path).parent, env=env, capture_output=True, text=True,
                check=False,
            )
            try:
                parsed = json.loads(proc.stdout)
            except json.JSONDecodeError as error:
                raise ValueError(f"{fmt} CLI probe produced invalid JSON") from error
            if fmt == "json":
                actual_count = sum(len(row["structural_findings"]) for row in parsed)
                if len(parsed) != 1 or parsed[0]["verdict"] != verdicts[path]:
                    raise ValueError("JSON CLI verdict mismatch")
                if parsed[0]["gate"]["status"] != "evaluated":
                    raise ValueError("JSON CLI did not use the default gate")
                if (parsed[0]["gate"]["raw_findings"] != expected_raw or
                        parsed[0]["gate"]["suppressed"] != expected_raw - expected_count):
                    raise ValueError("JSON CLI default suppression mismatch")
                expected_format_count = expected_count
            elif fmt == "sarif":
                actual_count = sum(len(run["results"]) for run in parsed["runs"])
                expected_format_count = expected_count
            else:
                actual_count = len(parsed)
                expected_format_count = sum(f.source_region is not None for f in delivered_by_file[path])
            if actual_count != expected_format_count:
                raise ValueError(f"{fmt} CLI delivered finding count mismatch")
            # GitLab returns 1 if an unlocated finding cannot be serialized.
            format_exit = expected_exit or int(fmt == "gitlab" and expected_format_count < expected_count)
            if proc.returncode != format_exit:
                raise ValueError(f"{fmt} CLI exit mismatch")
            file_rows.append({"format": fmt, "delivered": actual_count,
                              "expected_exit": format_exit, "actual_exit": proc.returncode})
        probe_rows.append({"source_sha256": sha(Path(path).read_bytes()),
                           "raw_findings": expected_raw,
                           "suppressed": expected_raw - expected_count,
                           "verdict": verdicts[path], "formats": file_rows})
    return {"files": len(paths), "checks": probe_rows,
            "boundary": "Two representative files, not a subprocess per corpus file. "
                        "GitLab omits unlocated findings and returns 1 in that case."}


def replay() -> dict:
    from lintlang.gate import FPGate
    from lintlang.parsers import read_file_text
    from lintlang.report import compute_verdict
    from lintlang.scanner import scan_file

    manifest = read(MANIFEST)
    frozen_summary = read(FROZEN / "summary.json")
    frozen_raw = read(FROZEN / "candidate.json")
    frozen_gated = read(FROZEN / "candidate-gated.json")
    labeled = read(LABELS)
    verify_manifest(manifest, frozen_summary)
    raw_ref = checked_map(frozen_raw, "frozen raw")
    gated_ref = checked_map(frozen_gated, "frozen gated")
    label_ref = checked_map(labeled, "labeled")
    if raw_ref.keys() != gated_ref.keys() or raw_ref.keys() != label_ref.keys():
        raise ValueError("Frozen raw, gate, and adjudication identities differ")
    model_before = digest_tree(model_files())
    detector_before = digest_tree(detector_files())
    if read(ARTIFACTS / "thresholds.json") != {"keep": 0.85, "dismiss": 0.15}:
        raise ValueError("Default thresholds changed")
    classifier = FPGate()

    raw_now: dict[tuple, dict] = {}
    delivered_now: dict[tuple, dict] = {}
    by_file: dict[str, list] = {}
    raw_counts: dict[str, int] = {}
    verdicts: dict[str, str] = {}
    status_counts: Counter[str] = Counter()
    files_with_findings = 0
    for item in manifest["files"]:
        path = item["path"]
        raw = scan_file(path, gate=False)
        gated = scan_file(path)  # the real default, including DISMISS filtering
        if raw.input_error or gated.input_error or gated.gate_error:
            raise ValueError("Corpus scan or default gate unavailable")
        if gated.gate_status != "evaluated" or gated.gate_thresholds != {"keep": 0.85, "dismiss": 0.15}:
            raise ValueError("Default gate status or thresholds changed")
        if gated.raw_findings_count != len(raw.structural_findings):
            raise ValueError("Gate raw count differs from raw scan")
        if gated.suppressed_count != len(raw.structural_findings) - len(gated.structural_findings):
            raise ValueError("Suppression count mismatch")
        if raw.structural_findings:
            files_with_findings += 1
        status_counts[gated.gate_status] += 1
        verdicts[path] = compute_verdict(gated)
        by_file[path] = gated.structural_findings
        raw_counts[path] = len(raw.structural_findings)
        source_text = (Path(path).read_text(encoding="utf-8", errors="ignore")
                       if Path(path).suffix == ".py" else read_file_text(path))
        for finding in raw.structural_findings:
            key = identity(path, finding)
            if key in raw_now:
                raise ValueError("Duplicate current raw finding identity")
            raw_now[key] = {"severity": finding.severity.value}
            if key not in gated_ref:
                raise ValueError("Current raw finding absent from frozen gate receipt")
            decision, score = classifier.classify({
                "rule": finding.code, "severity": finding.severity.value,
                "pattern_name": finding.pattern_name, "evidence": finding.evidence,
                "context": source_text, "file_path": path,
            })
            frozen = gated_ref[key]
            if decision != frozen["gate_decision"] or round(score, 6) != frozen["gate_probability"]:
                raise ValueError("Model decision or score changed from frozen gate receipt")
        for finding in gated.structural_findings:
            key = identity(path, finding)
            if key in delivered_now:
                raise ValueError("Duplicate current delivered finding identity")
            delivered_now[key] = {"decision": finding.gate_decision,
                                  "score": finding.gate_probability,
                                  "severity": finding.severity.value}
        if sha(Path(path).read_bytes()) != item["sha256"]:
            raise ValueError("Corpus source changed during replay")

    if raw_now.keys() != raw_ref.keys():
        raise ValueError("Raw detector identities changed from frozen candidate")
    if raw_now.keys() != label_ref.keys():
        raise ValueError("Adjudicated labels do not cover current raw findings")
    expected_delivered = {key for key, row in gated_ref.items()
                          if row["gate_decision"] != "DISMISS"}
    if delivered_now.keys() != expected_delivered:
        raise ValueError("Default delivery differs from frozen gate decisions")
    for key, row in delivered_now.items():
        frozen = gated_ref[key]
        if (row["decision"] != frozen["gate_decision"] or
                row["score"] != frozen["gate_probability"] or
                row["severity"] != frozen["severity"]):
            raise ValueError("Default gate decision, score, or severity changed")
    if digest_tree(model_files()) != model_before or digest_tree(detector_files()) != detector_before:
        raise ValueError("Model or detector source changed during replay")

    by_decision: dict[str, Counter] = defaultdict(Counter)
    by_rule: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    private_rows = []
    for key in sorted(raw_now, key=str):
        frozen = gated_ref[key]
        decision = frozen["gate_decision"]
        label = label_ref[key]["label"]
        rule = frozen["identity"][0]
        if label not in {"TP", "FP", "UNRESOLVED"}:
            raise ValueError("Invalid adjudicated label")
        by_decision[decision][label] += 1
        by_rule[rule][decision][label] += 1
        private_rows.append({"finding_id": label_ref[key]["finding_id"],
                             "path": frozen["path"], "identity": frozen["identity"],
                             "severity": frozen["severity"], "label": label,
                             "label_provenance": label_ref[key]["label_provenance"],
                             "gate_decision": decision,
                             "gate_probability": frozen["gate_probability"],
                             "delivered": key in delivered_now})
    PRIVATE.mkdir(parents=True, exist_ok=True)
    write(PRIVATE / "per-finding.json", private_rows)
    write(PRIVATE / "run-context.json", {
        "manifest_sha256": sha(MANIFEST.read_bytes()), "model_file_sha256": model_before,
        "detector_file_sha256": detector_before,
        "label_file_sha256": sha(LABELS.read_bytes()),
        "frozen_raw_sha256": sha((FROZEN / "candidate.json").read_bytes()),
        "frozen_gated_sha256": sha((FROZEN / "candidate-gated.json").read_bytes()),
    })
    probes = cli_probes(choose_probes(frozen_gated), by_file, raw_counts, verdicts)
    summary = {
        "status": "MATCH_FROZEN_DEFAULT_GATE",
        "release_readiness": "BLOCKED_KEEP_PRECISION_BELOW_99_PERCENT",
        "scope": "Frozen 0.8.8 development corpus; AI-review labels are not independent population truth.",
        "files": len(manifest["files"]), "files_with_raw_findings": files_with_findings,
        "manifest_sha256": sha(MANIFEST.read_bytes()),
        "corpus_source_hashes_verified": len(manifest["files"]),
        "corpus_sources_unchanged_during_replay": True,
        "label_file_sha256": sha(LABELS.read_bytes()),
        "model_artifact_sha256": model_before,
        "detector_source_tree_sha256": sha(json.dumps(detector_before, sort_keys=True).encode()),
        "default_thresholds": {"keep": 0.85, "dismiss": 0.15},
        "raw_findings": len(raw_now), "raw_identity_matches_frozen_candidate": True,
        "raw_detector_source_unchanged_during_replay": True,
        "default_gate_status_by_file": dict(sorted(status_counts.items())),
        "default_delivered_findings": len(delivered_now),
        "suppressed_findings": len(raw_now) - len(delivered_now),
        "suppressed_labeled_tp": by_decision["DISMISS"]["TP"],
        "suppressed_labeled_fp": by_decision["DISMISS"]["FP"],
        "keep_precision_on_resolved_labels": (
            by_decision["KEEP"]["TP"] /
            (by_decision["KEEP"]["TP"] + by_decision["KEEP"]["FP"])
        ),
        "keep_precision_target": 0.99,
        "model_and_detector_files_unchanged_during_replay": True,
        "delivery_matches_frozen_candidate_gated_excluding_dismiss": True,
        "all_gate_scores_match_frozen_candidate": True,
        "decisions_by_label": {d: dict(sorted(c.items())) for d, c in sorted(by_decision.items())},
        "by_rule_and_decision": {r: {d: dict(sorted(c.items())) for d, c in sorted(ds.items())}
                                 for r, ds in sorted(by_rule.items())},
        "verdicts_by_file": dict(sorted(Counter(verdicts.values()).items())),
        "cli_format_probes": probes,
        "boundary": "Default gate removes DISMISS findings from delivered output. KEEP blocks, ESCALATE is advisory. "
                    "Identity and score agreement with the frozen receipt establishes unchanged behavior on these files, "
                    "not production precision or safety. Raw paths, evidence, labels by identity, and source text stay private.",
    }
    write(PUBLIC, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    summary = replay()
    print(json.dumps({key: summary[key] for key in ("status", "files", "raw_findings",
                                                    "default_delivered_findings", "suppressed_findings")},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
