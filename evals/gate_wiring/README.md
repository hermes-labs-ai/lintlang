# Default gate wiring development evidence

Current candidate: private 0.9.0, pending owner review.
[Current replay](current-results.json) checks all 1,599 frozen files against the
972 original finding labels: KEEP 179 TP / 10 FP, 94.71% observed precision.
Run `PYTHONPATH=src python evals/gate_wiring/replay_current.py`.
Historical receipts below remain historical; public publication is held.
See the [draft review report](../../docs/release-0.9.0.md).

## Current H1.8 language normalization

[Mined phrase tables](h18-language-mining.md) and the
[replay receipt](h18-language-results.json) cover the frozen 172 FP / 126 TP KEEP
cohort. Full tagged descriptions and exhaustive bounded phrase inventories stay
in `.hermes/local/h18-language/`. Reproduce with
`PYTHONPATH=src python3 evals/gate_wiring/mine_h18_languages.py`.
The English trigger regex, other rules, labels, and gate parameters are unchanged.
This development replay does not establish release precision or held-out accuracy.

## Earlier H5 retirement and H1.8 analysis

[H1.8 analysis](h18-analysis.md) records the corrected cohort counts and matched
examples. [H5 removal replay](h5-removal-results.json) measures 185 TP / 172 FP
in KEEP (**51.82% precision**) and **39.60% visible FP share**. These receipts
precede language normalization, when H1.8 and gate parameters were unchanged.
Reproduce that earlier state from commit `83e8fdb` with
`PYTHONPATH=src python evals/gate_wiring/scoping_replay.py --retired-h5` and
`PYTHONPATH=src python evals/gate_wiring/analyze_h18.py`.

## Earlier scoping replay (before H5 retirement)

See [scoping-results.json](scoping-results.json) and the current scoping section
of [the release report](../../docs/release-0.8.8.md). Run
`PYTHONPATH=src python evals/gate_wiring/scoping_replay.py` to reproduce.
The prior `replay.py` and `results.json` below retain the explicit-file baseline;
the new replay separately measures directory scope without overwriting it.

After directory scoping, KEEP has 186 TP, 481 FP and one unresolved: **27.89%**
resolved precision. Visible findings have 364 TP, 547 FP and one unresolved:
**60.04%** resolved FP share. KEEP FPs are H1.8 (172) and H5 (309).
The 972-finding cohort has no H1.1 and only one finding in the newly excluded
directories; it cannot reproduce the separate 3,419-finding diligence percentages.
No weights or thresholds changed. All remote effects are held for owner review.

## Reproduce

Use the corrected candidate checkout with its private frozen corpus and review
packet under `.hermes/local/`. No network, labeling or model training occurs in
replay. The private packet is intentionally excluded from Git and distributions.

```sh
python .hermes/local/release-088-labeling/aggregate.py
python evals/gate_wiring/replay.py
pytest -q
ruff check src/ tests/
python -m build --outdir .hermes/local/gate-wiring-dist
python -m twine check .hermes/local/gate-wiring-dist/*
python scripts/smoke_distributions.py .hermes/local/gate-wiring-dist
```

`replay.py` verifies every one of 1,599 source digests, checks raw identities
against the frozen corrected candidate, checks default delivered findings against
KEEP/ESCALATE identities, and joins labels by exact finding identity. It fails on
unknown labels, altered identities, unexpected suppression, unavailable models or
changed decisions. Representative CLI probes exercise JSON, SARIF and GitLab.
[results.json](results.json) contains only aggregate counts and digests.
[Historical reconciliation](../release_088/README.md) retains the Muse comparison.

## What the labels supported before scoping

[label-review.json](label-review.json) records the expanded 972-finding review:
377 TP, 594 FP and one unresolved. The 490 new items had two independent,
score-blind Sol passes (312 H5, 178 H1.8), with 489 agreements. H5 agreement was
99.68%, kappa 0.665; H1.8 agreement was 100%, with kappa undefined because both
reviewers assigned the same category throughout. The one disagreement remains
unresolved. Two parsed YAML quotations were replaced with verbatim source-line
quotes without changing their labels or reasons; the aggregate verifies every
review quote against the source file.

Historical labels were retained unchanged and were produced under a different
review process. New AI agreement is not human ground truth. The combined metrics
are mixed-provenance development evidence, not an independent held-out estimate.
Even the expanded unknown cohort alone contains 481 agreed FP among 483 KEEP
findings, so the original small-subset precision cannot support release approval.

KEEP precision is 186/668 = 27.84% on resolved labels (27.80–27.95% including the
unresolved item either way). The >99% target fails. Visible FP share is
548/912 = 60.09%; raw FP share is 594/971 = 61.17%. These are shares of emitted
findings, not the statistical false-positive rate among all negative inputs.
Thirteen labeled TP findings are suppressed. Wiring did not change detector
logic, model weights or thresholds, and does not improve classification accuracy.

## Independent reviews

An independent Astra code review reproduced two explicit policy interactions:
`--min-severity` can filter KEEP and `--fail-under` can independently block an
all-ESCALATE scan. CLI help, migration notes and regressions now state both.
An external subscription Claude review recommended withholding default approval
on incomplete labels. It was an AI review, not an actual ESLint developer.
The raw local review incorrectly suggested no existing baseline facility and
named the previous version incorrectly; neither claim is used here.

Four logged Jev calls tested finite policy choices and six synthetic actionability
examples in both option orders. Choices were stable, but 18/20 confidence values
were below 0.75: advisory escalation, not acceptance evidence. Full local pilot:
`jev-lab/pilots/lintlang-088-blocking-evidence-20261008/` in the local lab checkout.
No Jev runtime dependency was introduced.

## Pending handoff

The owner selected the corrected canonical architecture for preparation toward
private `hermes-labs-ai/lintlang-088-candidate:release/0.8.8`. The original private
Muse source remains at `fa691c0f7580b56500553b7dd6776a04deecd9a4`; it has not
been overwritten. Code lives on local `codex/lintlang-088-release`, based on
canonical `5ed167ace815b97ec004eeef98a05a46e6790a0d`. Local artifacts and exact
validation receipts are under `.hermes/local/gate-wiring-verification/` and
`.hermes/local/gate-wiring-dist/`. Commit/remote promotion remains pending owner
review; numerical release acceptance remains blocked regardless of engineering
checks passing.
