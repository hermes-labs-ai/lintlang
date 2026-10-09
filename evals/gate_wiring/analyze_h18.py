#!/usr/bin/env python3
"""Compare frozen H1.8 labels without changing them or the detector.

Read full front matter rather than the finding's truncated evidence. Raw rows
remain private; the output records aggregates and a small set of review examples.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median

from replay import LABELS, MANIFEST, ROOT, read, sha, write


def describe(rows: list[dict]) -> dict:
    lengths = [row["length"] for row in rows]
    return {
        "count": len(rows),
        "unique_descriptions": len({row["description"] for row in rows}),
        "length_codepoints": {"min": min(lengths), "median": median(lengths), "max": max(lengths)},
        "under_120_characters": sum(length < 120 for length in lengths),
        "severity": dict(Counter(row["severity"] for row in rows)),
        "file_extensions": dict(Counter(Path(row["path"]).suffix for row in rows)),
        "repositories": dict(Counter(row["repository"] for row in rows)),
        "path_prefixes": dict(Counter("/".join(row["relative_path"].split("/")[:2]) for row in rows)),
        "label_provenance": dict(Counter(row["label_provenance"] for row in rows)),
    }


def main() -> None:
    from lintlang.detectors.h1 import _SKILL_TRIGGER
    from lintlang.parsers import parse_source, read_file_text

    labels, manifest = read(LABELS), read(MANIFEST)
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    assert len(labels) == 972
    detector = ROOT / "src/lintlang/detectors/h1.py"
    detector_hash = sha(detector.read_bytes())
    rows = []
    for row in labels:
        if row["identity"][0] != "H1.8":
            continue
        path = Path(row["path"])
        assert sha(path.read_bytes()) == expected[str(path)]
        skill = parse_source(read_file_text(path), path).skill
        assert skill is not None
        description = skill.description.strip()
        assert not _SKILL_TRIGGER.search(description)
        parts = path.parts
        start = parts.index("repos") + 1
        rows.append({**row, "description": description, "length": len(description),
                     "repository": parts[start], "relative_path": "/".join(parts[start + 1:])})
    tp = [r for r in rows if r["label"] == "TP"]
    keep_tp = [r for r in tp if r["gate_decision"] == "KEEP"]
    keep_fp = [r for r in rows if r["label"] == "FP" and r["gate_decision"] == "KEEP"]
    expanded = [r for r in rows if r["label_provenance"] == "new_double_blind_ai"]
    by_skill_tp = {Path(r["path"]).parent.name for r in keep_tp}
    by_skill_fp = {Path(r["path"]).parent.name for r in keep_fp}
    example_paths = {
        "docs/zh-CN/skills/golang-testing/SKILL.md",
        "docs/ja-JP/skills/python-testing/SKILL.md",
        "docs/tr/skills/verification-loop/SKILL.md",
        "docs/zh-TW/skills/golang-testing/SKILL.md",
        "docs/tr/skills/python-testing/SKILL.md",
        "docs/ja-JP/skills/quarkus-tdd/SKILL.md",
    }
    examples = [{k: r[k] for k in ("finding_id", "label", "label_provenance", "repository",
                                  "relative_path", "description", "length", "severity")}
                for r in rows if r["relative_path"] in example_paths]
    assert len(examples) == 6
    assert sha(detector.read_bytes()) == detector_hash
    result = {
        "manifest_sha256": sha(MANIFEST.read_bytes()), "label_sha256": sha(LABELS.read_bytes()),
        "historical_seed_sha256": manifest["seed_sha256"], "h1_source_sha256": detector_hash,
        "historical_tp": describe(tp), "keep_tp": describe(keep_tp), "keep_fp": describe(keep_fp),
        "expanded_fp": describe(expanded), "examples": examples,
        "same_skill_directory_names_in_both_keep_label_groups": len(by_skill_tp & by_skill_fp),
        "exact_descriptions_with_conflicting_tp_and_keep_fp_labels": len(
            {r["description"] for r in tp} & {r["description"] for r in keep_fp}),
        "boundary": "Frozen 972-finding development cohort. Labels are unchanged historical/AI judgments, "
                    "not newly confirmed ground truth. Counts do not reproduce the claimed 150 TP cohort. "
                    "Path locale is not a language classifier; translated copies are not independent tasks. "
                    "Length is Unicode code points, not tokens. H1.8 code and all gate parameters are unchanged.",
    }
    write(ROOT / "evals/gate_wiring/h18-analysis.json", result)
    print(json.dumps({key: result[key] for key in ("historical_tp", "keep_tp", "keep_fp")}, indent=2))


if __name__ == "__main__":
    main()
