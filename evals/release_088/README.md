# 0.8.8 reference-corpus replay

This is the historical detector reconciliation and annotation-only gate snapshot.
Current default-on wiring is measured separately in [gate wiring](../gate_wiring/README.md).
For the historical command below, use the frozen pre-wiring source tree; current
source intentionally no longer meets the annotation-only assertion.

`compare.py` replays a frozen file manifest through `scan_file` from two isolated
source trees and the unmodified Muse vendor source at `fa691c0`. It checks each
input hash, records all source-tree hashes, uses
exact `(file, rule, location, line, description, evidence)` identities to transfer
historical labels, then compares detector retention by `(file, rule, location,
line, evidence)` so a diagnostic wording change does not masquerade as lost
detection. Ambiguous non-H6 retention identities fail the run. H6 retirement is
reported separately.
Private per-finding output identifies every lost or added finding for review.
Muse is scanned both raw (`gate=False`) and with its native default gate, which
removes DISMISS findings. The reconciled candidate's gate is opt-in and
annotation-only.

The retained historical development corpus has 499 model-reviewed labels
(376 TP, 123 FP). Available current source snapshots support exact finding and
verbatim-context transfer for 497 labels (376 TP, 121 FP). Two historical FP
identities have no transferred source match. There is no independent human
adjudication or historical full-file digest for this cohort. This evidence can
establish observed retention against these reference labels; it cannot establish
population precision or an independently verified zero-loss claim.

The private manifest schema is an object with `seed_sha256`, `seed_labels`,
`files` (objects with absolute `path` and `sha256`) and `references` (objects with
unique `id`, `label` = `tp`/`fp`, `path`, and five-element `identity` array:
rule, location, start line or null, description, evidence). Keep its source data
and `baseline.json`, `candidate.json`, and `private-delta.json` local. Only
`summary.json` contains publishable aggregates and hashes.

Example, with dependencies already installed in the selected Python environment:

```sh
python evals/release_088/compare.py \
  --manifest /private/corpus/manifest.json \
  --baseline-src /private/baseline/src \
  --candidate-src .hermes/local/gate-wiring-baseline/src \
  --muse-src /private/muse/vendor/lintlang-0.8.0 \
  --output .hermes/local/release-088-eval/final \
  --gate-candidate \
  --public-output evals/release_088/results.json
```

Extract the baseline from commit `5ed167ace815b97ec004eeef98a05a46e6790a0d`
and Muse source from `fa691c0f7580b56500553b7dd6776a04deecd9a4` using
`git archive`, and use the same manifest for every variant. After a full replay,
`--reuse-records` recomputes aggregates from saved private records only when
the manifest and all source hashes still match. No provider
requests, refitting, threshold tuning, or label changes occur. `PASS_REFERENCE_TP_RETENTION`
means all reference TPs existed at baseline and none were lost (except H6,
reported separately). It does not approve unexplained unknown removals or
classifier suppression; those remain distinct release gates. `--gate-candidate`
replays the candidate with advisory gate enabled, fails if annotation fails or
the delivered finding multiset changes, and reports KEEP/ESCALATE/DISMISS counts
by rule and transferred reference label. The private gated records stay local;
only aggregates appear in `summary.json`. CLI/formatter, packaging, and synthetic
regression checks remain separate.

The frozen 1,599-file development replay is in [results.json](results.json).
All 376 transferred TP references were present at baseline and in the
reconciled raw scanner by stable detection identity; H6 has no transferred TP
labels and is counted separately. The exact diagnostic prose changed for two
retained TPs. Rule-level retained counts are in the JSON receipt.

| Variant | Raw findings | Transferred TPs retained | Transferred FPs removed | Gate delivery |
| --- | ---: | ---: | ---: | --- |
| Baseline `5ed167a` | 1,159 | 376/376 | 0/121 | No gate |
| Unmodified Muse `fa691c0` | 1,094 | 369/376 | 10/121 | Default gate delivers 40/1,094; suppresses all 369 labeled TPs still detected |
| Reconciled 0.8.8 | 972 | 376/376 | 15/121 | Optional gate annotates all 972 findings |

The reconciled classifier marks 185 TPs KEEP, 178 ESCALATE, and 13 DISMISS;
among the 106 surviving transferred FPs, it marks 1 KEEP, 59 ESCALATE, and
46 DISMISS. The decisions cannot safely remove findings. On transferred labels,
current `--fail-on fail` severity logic selects one FP and no TP; `--fail-on
review` selects 375 TPs and 106 FPs. A hypothetical KEEP-only review set has
184 TPs and 1 FP, but would leave the other 191 review-level TPs outside that
set. These are development-label diagnostics, not an independently validated
default policy.

Muse's release notes claimed 100% TP retention, greater than 25% FP reduction,
and roughly 20% additional gate FP filtering. This frozen replay does not
support those claims: its raw scanner loses seven labeled TPs, while the native
default gate suppresses every remaining labeled TP. The original gate passes
malformed subrule IDs such as `H1.H1.8`, empty source context, and (because of
path extraction precedence) an empty file path into its 34-feature model. The
reconciled gate passes stable IDs, actual source context, and file paths. These
input changes explain why decisions can differ, but this replay does not isolate
their individual causal effects. The historical claim that H6 removed 67 FPs
cannot be verified on this transferred cohort: its 170 removals are unlabeled.
Two historical FP identities also lack current source matches, so no
population FP rate follows from these counts.
