#!/usr/bin/env python3
"""Replay a private, hash-bound corpus against two source trees; emit safe aggregates.

No model calls, dependency installation, label changes, or source discovery.
The manifest is private and must never be committed with this runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_hashes(source):
    root = Path(source)
    return {str(p.relative_to(root)): digest(p.read_bytes())
            for p in sorted(root.rglob("*.py"))}


def worker(manifest, output, gate_mode="none"):
    from lintlang.scanner import scan_file

    records = []
    for item in manifest["files"]:
        path = Path(item["path"])
        if digest(path.read_bytes()) != item["sha256"]:
            raise ValueError("Corpus source hash changed")
        result = (scan_file(path) if gate_mode == "none" else
                  scan_file(path, gate=gate_mode in {"advisory", "native"}))
        if result.input_error:
            raise ValueError(f"Corpus input error: {path}")
        if gate_mode == "advisory" and result.gate_status not in {"evaluated", "not_needed"}:
            raise ValueError(f"Gate unavailable for corpus source: {path}")
        for f in result.structural_findings:
            records.append({"path": str(path), "identity": [
                f.code, f.location,
                f.source_region.start_line if f.source_region else None,
                f.description, f.evidence], "severity": f.severity.value,
                **({"gate_decision": f.gate_decision, "gate_probability": f.gate_probability}
                   if gate_mode in {"advisory", "native"} else {})})
    write(output, records)


def key(row):
    return (row["path"], *row["identity"])


def stable_key(row):
    """Finding identity excluding diagnostic prose and severity."""
    path, (rule, location, line, _description, evidence) = row["path"], row["identity"]
    return path, rule, location, line, evidence


def unique_stable(rows):
    """Reject ambiguous non-H6 matches; H6 is retired and counted separately."""
    counts = Counter(stable_key(row) for row in rows if row["identity"][0] != "H6")
    ambiguous = [identity for identity, count in counts.items() if count > 1]
    if ambiguous:
        raise ValueError(f"Ambiguous stable finding identities: {len(ambiguous)}")
    return {stable_key(row): row for row in rows}


def native_gate_summary(raw, gated, references):
    """Measure original Muse default behavior, including actual suppression."""
    before, after = {key(row): row for row in raw}, {key(row): row for row in gated}
    if len(before) != len(raw) or len(after) != len(gated):
        raise ValueError("Duplicate full finding identities in Muse replay")
    if after.keys() - before.keys():
        raise ValueError("Muse gate introduced detector findings")
    refs = {stable_key(row): row['label'] for row in references}
    dropped = before.keys() - after.keys()
    kept = before.keys() & after.keys()
    return {
        "raw_findings": len(raw), "default_delivered_findings": len(gated),
        "suppressed": len(dropped),
        "suppressed_by_reference_label": dict(Counter(refs.get(stable_key(before[k]), "unknown") for k in dropped)),
        "suppressed_by_rule": dict(Counter(k[1] for k in dropped)),
        "delivered_by_gate_decision": dict(Counter(after[k].get("gate_decision") for k in kept)),
        "labeled_raw": dict(Counter(refs.get(stable_key(row), "unknown") for row in raw)),
        "labeled_delivered": dict(Counter(refs.get(stable_key(row), "unknown") for row in gated)),
        "boundary": "Unmodified Muse scan_file default gate=True actually removes DISMISS findings. Missing findings are counted as suppressed, not inferred to be false positives.",
    }


def muse_candidate_decision_delta(muse_raw, muse_gated, candidate_gated, references):
    """Compare decisions only where both scanners produced one exact finding."""
    muse = {key(row): row for row in muse_raw}
    delivered = {key(row): row for row in muse_gated}
    candidate = {key(row): row for row in candidate_gated}
    refs = {stable_key(row): row['label'] for row in references}
    shared = muse.keys() & candidate.keys()
    transitions = Counter()
    by_label = {'tp': Counter(), 'fp': Counter(), 'unknown': Counter()}
    for identity in shared:
        before = delivered[identity].get('gate_decision') if identity in delivered else 'DISMISS'
        after = candidate[identity]['gate_decision']
        transition = f'{before}->{after}'
        transitions[transition] += 1
        by_label[refs.get(stable_key(muse[identity]), 'unknown')][transition] += 1
    return {
        'shared_exact_finding_identities': len(shared),
        'transitions': dict(sorted(transitions.items())),
        'by_reference_label': {label: dict(sorted(counts.items()))
                               for label, counts in by_label.items()},
        'boundary': 'Shared exact findings only. Muse DISMISS is inferred from the unchanged source gate filtering; candidate decisions are delivered annotations. Rule ID and context inputs changed simultaneously, so this is a behavior comparison, not a causal attribution.',
    }


def gate_summary(candidate, gated, references):
    """Prove advisory delivery preserves identities and count labeled decisions."""
    raw_keys = [key(row) for row in candidate]
    gated_keys = [key(row) for row in gated]
    if Counter(raw_keys) != Counter(gated_keys):
        raise ValueError("Gate changed delivered detector finding identities")
    refs = {stable_key(row): row["label"] for row in references}
    decisions = Counter()
    labeled = {"tp": Counter(), "fp": Counter(), "unknown": Counter()}
    by_rule = {}
    labeled_records = []
    for row in gated:
        decision = row.get("gate_decision")
        if decision not in {"KEEP", "ESCALATE", "DISMISS"}:
            raise ValueError("Missing or invalid gate decision")
        decisions[decision] += 1
        labeled[refs.get(stable_key(row), "unknown")][decision] += 1
        by_rule.setdefault(row["identity"][0], Counter())[decision] += 1
        if stable_key(row) in refs:
            labeled_records.append((refs[stable_key(row)], row))
    blocking = {}
    for level, severities in {
        "fail": {"critical", "high"},
        "review": {"critical", "high", "medium"},
    }.items():
        records = [(label, row) for label, row in labeled_records if row["severity"] in severities]
        raw_counts = Counter(label for label, _row in records)
        keep_counts = Counter(label for label, row in records if row["gate_decision"] == "KEEP")
        blocking[level] = {
            "raw_labeled": dict(raw_counts),
            "keep_labeled": dict(keep_counts),
            "raw_precision": (raw_counts['tp'] / sum(raw_counts.values())
                              if raw_counts else None),
            "keep_precision": (keep_counts['tp'] / sum(keep_counts.values())
                               if keep_counts else None),
            "note": "Current --fail-on uses raw severity and is unchanged by the optional gate. KEEP numbers are hypothetical selection diagnostics.",
        }
    operating_points = {}
    for threshold in (0.5, 0.85, 0.9, 0.95, 0.99):
        chosen = Counter(label for label, row in labeled_records
                         if row["gate_probability"] >= threshold)
        operating_points[str(threshold)] = {
            "tp": chosen['tp'], "fp": chosen['fp'],
            "precision": chosen['tp'] / sum(chosen.values()) if chosen else None,
            "tp_recall_on_candidate_labels": chosen['tp'] / labeled['tp'].total()
            if labeled['tp'] else None,
        }
    return {
        "status": "PASS_ANNOTATION_ONLY",
        "delivered_findings": len(gated),
        "raw_findings": len(candidate),
        "decisions": dict(decisions),
        "by_reference_label": {label: dict(counts) for label, counts in labeled.items()},
        "by_rule": {rule: dict(counts) for rule, counts in sorted(by_rule.items())},
        "blocking_severity_diagnostics": blocking,
        "score_operating_points": operating_points,
        "boundary": "Decisions annotate every detector finding without changing delivered identities. Current --fail-on is based on raw severity. KEEP and fixed score thresholds are exploratory diagnostics on transferred development labels, not tuned or independently validated release policies. Scores are model estimates, not calibrated probabilities or independent truth labels.",
    }


def compare(manifest, baseline, candidate):
    old, new = {key(r): r for r in baseline}, {key(r): r for r in candidate}
    old_stable, new_stable = unique_stable(baseline), unique_stable(candidate)
    refs = {key(r): r for r in manifest["references"]}
    if len(refs) != len(manifest["references"]):
        raise ValueError("Duplicate reference finding identities")
    if len({r['id'] for r in refs.values()}) != len(refs):
        raise ValueError("Duplicate reference IDs")
    rules = sorted({r["identity"][0] for r in baseline + candidate} |
                   {r["identity"][0] for r in refs.values()})
    by_rule = {}
    for rule in rules:
        before = {k for k in old if k[1] == rule}
        after = {k for k in new if k[1] == rule}
        row = {"baseline": len(before), "candidate": len(after),
               "removed": len(before - after), "added": len(after - before)}
        for label in ("tp", "fp"):
            labeled = {k for k, r in refs.items() if r['label'] == label and k[1] == rule}
            row.update({f"reference_{label}": len(labeled),
                        f"baseline_{label}": len(before & labeled),
                        f"candidate_{label}": len(after & labeled),
                        f"lost_{label}": len((before - after) & labeled)})
        row['removed_unknown'] = len((before - after) - refs.keys())
        row['added_unknown'] = len((after - before) - refs.keys())
        if rule != 'H6':
            before_stable = {k for k in old_stable if k[1] == rule}
            after_stable = {k for k in new_stable if k[1] == rule}
            labeled_stable = {stable_key(r): r for r in refs.values() if r['identity'][0] == rule}
            row['stable_removed'] = len(before_stable - after_stable)
            row['stable_added'] = len(after_stable - before_stable)
            row['stable_removed_unknown'] = len((before_stable - after_stable) - labeled_stable.keys())
            row['stable_baseline_tp'] = len({k for k in before_stable & labeled_stable.keys()
                                             if labeled_stable[k]['label'] == 'tp'})
            row['stable_candidate_tp'] = len({k for k in after_stable & labeled_stable.keys()
                                              if labeled_stable[k]['label'] == 'tp'})
            row['stable_baseline_fp'] = len({k for k in before_stable & labeled_stable.keys()
                                             if labeled_stable[k]['label'] == 'fp'})
            row['stable_candidate_fp'] = len({k for k in after_stable & labeled_stable.keys()
                                              if labeled_stable[k]['label'] == 'fp'})
            row['stable_lost_tp'] = len({k for k in before_stable - after_stable
                                         if labeled_stable.get(k, {}).get('label') == 'tp'})
            row['stable_lost_fp'] = len({k for k in before_stable - after_stable
                                         if labeled_stable.get(k, {}).get('label') == 'fp'})
            row['diagnostic_wording_changed'] = len({k for k in before_stable & after_stable
                                                       if key(old_stable[k]) != key(new_stable[k])})
        by_rule[rule] = row
    losses = [r['id'] for k, r in refs.items()
              if r['label'] == 'tp' and k in old and stable_key(r) not in new_stable and k[1] != 'H6']
    exact_losses = [r['id'] for k, r in refs.items()
                    if r['label'] == 'tp' and k in old and k not in new and k[1] != 'H6']
    missing = [r['id'] for k, r in refs.items() if r['label'] == 'tp' and k not in old]
    report = {
        "status": "PASS_REFERENCE_TP_RETENTION" if not losses and not missing else "BLOCKED",
        "files": len(manifest['files']), "reference_labels": dict(Counter(r['label'] for r in refs.values())),
        "historical_seed_labels": manifest['seed_labels'],
        "seed_sha256": manifest['seed_sha256'], "by_rule": by_rule,
        "non_h6_tp_losses": len(losses), "non_h6_exact_text_tp_changes": len(exact_losses),
        "reference_tp_missing_from_baseline": len(missing),
        "h6_separate": by_rule.get('H6', {}),
        "baseline_findings": len(baseline), "candidate_findings": len(candidate),
        "boundary": "Model-reviewed historical labels transferred by exact finding identity and verbatim context to current source snapshots. Retention compares path, rule, location, start line, and evidence, excluding diagnostic prose/severity; non-H6 identity collisions fail. Development corpus, not independently adjudicated population precision. Two historical FP identities have no transferred source match. H6 retirement is separate. Unknown additions/removals require review; this TP retention status alone is not release acceptance.",
    }
    private = {"lost_tp_ids": losses, "exact_text_changed_tp_ids": exact_losses,
               "missing_baseline_tp_ids": missing,
               "removed": [dict(old[k], reference_label=refs.get(k, {}).get('label', 'unknown'))
                           for k in sorted(old.keys() - new.keys(), key=str)],
               "added": [new[k] for k in sorted(new.keys() - old.keys(), key=str)]}
    return report, private


def public_summary(summary):
    """Aggregate-only release receipt with no private corpus paths or findings."""
    fields = ('status', 'files', 'historical_seed_labels', 'reference_labels',
              'reference_tp_missing_from_baseline', 'non_h6_tp_losses',
              'non_h6_exact_text_tp_changes', 'baseline_findings', 'candidate_findings',
              'by_rule', 'h6_separate', 'gate', 'muse_raw_vs_baseline',
              'muse_default_gate', 'muse_to_candidate_gate', 'seed_sha256',
              'manifest_sha256', 'runner_sha256', 'boundary')
    public = {field: summary[field] for field in fields if field in summary}
    public['source_tree_sha256'] = {
        name: digest(json.dumps(files, sort_keys=True).encode())
        for name, files in summary['source_sha256'].items()
    }
    public['baseline_commit'] = '5ed167ace815b97ec004eeef98a05a46e6790a0d'
    if 'muse-raw' in summary['source_sha256']:
        public['muse_commit'] = 'fa691c0f7580b56500553b7dd6776a04deecd9a4'
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--baseline-src', type=Path)
    parser.add_argument('--candidate-src', type=Path)
    parser.add_argument('--muse-src', type=Path,
                        help='Unmodified Muse vendor source extracted from fa691c0')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--public-output', type=Path,
                        help='Write aggregate-only, source-hashed receipt at this path')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--worker-gate-mode', choices=['none', 'raw', 'advisory', 'native'],
                        default='none')
    parser.add_argument('--gate-candidate', action='store_true',
                        help='Replay candidate with advisory gate and assert exact finding retention')
    parser.add_argument('--reuse-records', action='store_true',
                        help='Reaggregate saved records only after matching manifest and source hashes')
    args = parser.parse_args()
    manifest = read(args.manifest)
    if args.worker:
        worker(manifest, args.output, gate_mode=args.worker_gate_mode)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    previous = read(args.output / 'summary.json') if args.reuse_records else None
    if previous and previous['manifest_sha256'] != digest(args.manifest.read_bytes()):
        raise ValueError('Manifest changed since saved replay')
    before = {}
    sources = [('baseline', args.baseline_src), ('candidate', args.candidate_src)]
    if args.muse_src:
        sources.append(('muse-raw', args.muse_src))
    for name, source in sources:
        if source is None:
            parser.error('Both source paths are required')
        before[name] = source_hashes(source)
        if previous:
            if previous['source_sha256'][name] != before[name]:
                raise ValueError(f'{name} source changed since saved replay')
        else:
            env = dict(os.environ, PYTHONPATH=str(source.resolve()))
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                            '--worker-gate-mode', 'raw' if name == 'muse-raw' else 'none',
                            '--manifest', str(args.manifest.resolve()), '--output',
                            str((args.output / f'{name}.json').resolve())], env=env, check=True)
        if before[name] != source_hashes(source):
            raise ValueError('Source tree changed during evaluation')
    summary, details = compare(manifest, read(args.output / 'baseline.json'),
                               read(args.output / 'candidate.json'))
    if args.gate_candidate:
        source = args.candidate_src
        before_gate = source_hashes(source)
        if before_gate != before['candidate']:
            raise ValueError('Candidate source changed before gate evaluation')
        if not previous:
            env = dict(os.environ, PYTHONPATH=str(source.resolve()))
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                            '--worker-gate-mode', 'advisory', '--manifest', str(args.manifest.resolve()),
                            '--output', str((args.output / 'candidate-gated.json').resolve())],
                           env=env, check=True)
        if before_gate != source_hashes(source):
            raise ValueError('Candidate source changed during gate evaluation')
        summary['gate'] = gate_summary(read(args.output / 'candidate.json'),
                                      read(args.output / 'candidate-gated.json'),
                                      manifest['references'])
    if args.muse_src:
        source = args.muse_src
        before_gate = source_hashes(source)
        if before_gate != before['muse-raw']:
            raise ValueError('Muse source changed before default gate evaluation')
        if not previous:
            env = dict(os.environ, PYTHONPATH=str(source.resolve()))
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                            '--worker-gate-mode', 'native', '--manifest', str(args.manifest.resolve()),
                            '--output', str((args.output / 'muse-gated.json').resolve())],
                           env=env, check=True)
        if before_gate != source_hashes(source):
            raise ValueError('Muse source changed during default gate evaluation')
        muse_raw = read(args.output / 'muse-raw.json')
        muse_gated = read(args.output / 'muse-gated.json')
        muse_report, muse_details = compare(manifest, read(args.output / 'baseline.json'), muse_raw)
        summary['muse_raw_vs_baseline'] = {
            key: value for key, value in muse_report.items() if key not in {'boundary', 'seed_sha256'}
        }
        summary['muse_default_gate'] = native_gate_summary(muse_raw, muse_gated,
                                                           manifest['references'])
        if args.gate_candidate:
            summary['muse_to_candidate_gate'] = muse_candidate_decision_delta(
                muse_raw, muse_gated, read(args.output / 'candidate-gated.json'),
                manifest['references'])
        write(args.output / 'muse-private-delta.json', muse_details)
    summary['source_sha256'] = before
    summary['manifest_sha256'] = digest(args.manifest.read_bytes())
    summary['runner_sha256'] = digest(Path(__file__).read_bytes())
    write(args.output / 'summary.json', summary)
    write(args.output / 'private-delta.json', details)
    if args.public_output:
        write(args.public_output, public_summary(summary))
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_sha256'}, indent=2))
    if summary['status'] == 'BLOCKED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
