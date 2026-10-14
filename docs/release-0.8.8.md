# 0.8.8 release candidate (historical)

This report preserves earlier candidate measurements and holds. The current
private candidate is [0.9.0](release-0.9.0.md); its current metrics and scope
supersede the historical figures below.

This is an unpublished local candidate for the original session to review.
No PR, push, tag, GitHub release, or PyPI publication has been made.
The owner paused PR submission and selected precision for blocking findings,
with uncertain findings remaining advisory. Default-on wiring is implemented locally,
but release approval is **BLOCKED** because the expanded review fails the >99%
KEEP precision target. No detector rules or model parameters changed during wiring.

## H5 retirement (current)

H5 is removed entirely; `detect_h5` and explicit H5 selection are no longer
supported. The H1.8 detector is unchanged. See the [H1.8 comparison and H5
replay](../evals/gate_wiring/h18-analysis.md) for the cohort-count correction,
matched examples and current metrics. KEEP is 185 TP / 172 FP (**51.82%**);
visible FP share is 238 / 601 (**39.60%**). Retirement removes one historically
labeled H5 TP and one unresolved finding as well as its false positives.
The work remains local on `codex/lintlang-088-release`, held for owner review.

## Scoping fix replay (before H5 retirement)

The local scoping fix retires H1.1 for both tool and skill descriptions and adds
`tests`, `test`, `cassettes`, `fixtures`, `mocks`, `memory-tests`, `examples`,
`cookbook`, `tutorials`, and `lessons` to directory-component exclusions.
Exclusions are relative to the requested scan root; ancestor directory names
do not hide a project. Explicit-file scans still inspect these paths. Empty descriptions do not fall
through to H1.2. No other detector, model weight, scaler or threshold changed
relative to the preceding local candidate.

The 972-finding frozen cohort covers 1,599 hash-verified source files and contains
**no H1.1 findings**. It is different from the diligence report's 3,419-finding
cohort. The new directory exclusions remove one H5 false positive from this
cohort; no reference TP identity is lost by the scoping fix.

| Output after directory scope | TP | FP | Unresolved |
| --- | ---: | ---: | ---: |
| KEEP | 186 | 481 | 1 |
| Visible (KEEP + ESCALATE) | 364 | 547 | 1 |
| DISMISS | 13 | 46 | 0 |

KEEP precision: **27.89% = 186 / 667**. Visible false-positive share:
**60.04% = 547 / 911**. Percentages exclude the one unresolved finding.
This is FP/(TP+FP) among emitted findings, not FPR over all negative inputs.
KEEP still contains H1.8: **172 FP**, and H5: **309 FP**, so the requested 90%
reporting threshold is not met. No gate thresholds were adjusted.

The original explicit-file replay bypasses directory exclusions and is unchanged:
972 raw findings; KEEP 186 TP, 482 FP, one unresolved (**27.84%**); visible
364 TP, 548 FP, one unresolved (**60.09% FP share**). The directory-scoped
measurement applies the ten new component exclusions to the same frozen manifest;
it is not a fresh discovery scan or a new labeling exercise. Labels retain their
mixed historical/AI-review provenance and do not establish population accuracy.

Reproduce with `PYTHONPATH=src python evals/gate_wiring/scoping_replay.py`.
Aggregates and source/model digests: `evals/gate_wiring/scoping-results.json`.
Per-finding evidence remains private under `.hermes/local/scoping-fix/`.

Validation: 1,200 tests passed (the preceding 1,197 tests updated for the retired
rule plus three new scoping regressions), 4 expected failures and 76 subtests;
Ruff passed. Public push, PR, merge and publication remain held for owner review.
Work remains on `codex/lintlang-088-release` in the latest session's checkout.

## Reconciliation

The candidate starts at canonical `5ed167ace815b97ec004eeef98a05a46e6790a0d`.
The Muse implementation at `fa691c0f7580b56500553b7dd6776a04deecd9a4`
contains unrelated pipeline history and an older vendored package. Only the intended
detector and classifier changes were ported into `src/lintlang`; pipeline state,
queue logic and vendored architecture were not imported.

The work named 0.9.0 was inspected as earlier work from the same session, not as
an automatically newer release. Its H4 occurrence handling, encoding rejection,
pinned local corpus check, packaging privacy checks and released-Action smoke
correction were included selectively. Cursor discovery, multilingual trigger
expansion and unrelated example/plugin work remain separate. Existing open PRs
and the 1.0.0 experimental roadmap are not prerequisites or acceptance evidence.

## Migration

- H6 no longer runs. Remove H6 from explicit CLI pattern selections. The legacy
  `detect_h6` Python import remains a no-op; historical findings remain serializable.
- H1.7 retains a LOW notice above 1024 characters, distinguishes descriptions above
  2500 characters, and reports HIGH above 5000. Removing the 1025–2500 notice
  lost a labeled TP in the golden corpus, so that Muse relaxation was corrected. These are
  heuristic advisory thresholds, not assertions about a specific host's limits.
- H1.9 accepts case differences and explicit version suffix variants. Invalid or
  unrelated names still receive diagnostics; arbitrary substring overlap is insufficient.
- H4 excludes illustrative references by context and treats output/external/existence
  references per occurrence. Required missing inputs remain actionable even when
  their directory is named `examples`, `templates`, `prompts` or `fixtures`.
- NUL-containing text is an input error with a conversion hint, including BOM-less
  UTF-16/32 accidentally supplied where UTF-8 is required.

## Learned gate wiring (pending approval)

`lintlang scan PATH --format json` and `scan_file(path)` now enable the gate.
KEEP findings selected by the scan filters remain visible, produce FAIL, and exit 1
regardless of raw severity. Explicit `--min-severity`, pattern selections and baseline
allowances still narrow the findings evaluated for the verdict.
ESCALATE findings remain visible as REVIEW and do not block, even with
`--fail-on review`. DISMISS findings are hidden from every output format and the
Python findings list; diagnostics retain raw and suppressed counts.
`--no-gate` / `gate=False` restores the raw detector behavior. The deprecated
`--gate` alias remains accepted. `--gate-threshold KEEP[,DISMISS]` defaults to
`0.85,0.15`; a single value changes KEEP only. Thresholds must be finite and
satisfy `0 <= DISMISS < KEEP <= 1`. `--fail-under` remains an independent legacy
HERM score policy and can still cause failure.

The GitHub Action adds `gate: "false"` as the raw-mode opt-out; its default
`gate: "true"` uses KEEP blocking. Existing `fail-on` values retain their raw-mode
meaning. CI checks both raw severity behavior and default KEEP enforcement.

JSON includes decisions, scores, raw/suppressed counts and thresholds. SARIF maps
KEEP to error and ESCALATE to warning; GitLab maps KEEP to blocker and ESCALATE
to major. Raw mode retains the previous severity mapping. Invalid or missing
model artifacts produce ERROR/exit 1 and retain raw findings, including for an
otherwise empty scan. The classifier is offline pure Python with bundled JSON
parameters and no additional runtime dependency.

Scores are unverified model estimates, not calibrated confidence. The real model
suppresses a CRITICAL missing-description finding in the bundled bad sample.
Before H5 retirement, integration delivery tests exercised a retained H5 finding; they did
not prove retention of that original H1.1 fixture. This measured suppression and
the expanded false-positive review prevent release approval.

## Reproduction

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' build twine
.venv/bin/python -m pytest -q
.venv/bin/ruff check src/ tests/
.venv/bin/lintlang scan samples/clean_config.yaml --format json
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
.venv/bin/python scripts/smoke_distributions.py dist
```

The distribution smoke creates separate fresh environments for wheel and sdist,
installs each artifact, verifies dependency metadata and packaged model/schema
resources, and exercises Python and CLI JSON/SARIF/GitLab consumers outside the
checkout. The complete suite runs in CI on Python 3.10–3.13. Labeled-corpus
replay and final acceptance results are recorded separately below once complete.

## Blocking policy review

[ESLint rule configuration](https://eslint.org/docs/latest/use/configure/rules)
distinguishes errors that block CI from warnings suitable for uncertain findings
requiring review. This supports separate blocking and advisory channels, not a
universal zero-false-positive or 80-percent recall doctrine.
[Ruff's rule guidance](https://docs.astral.sh/ruff/linter/) likewise favors an
explicit gradual rule selection; security checks can intentionally prefer recall.

For this candidate, measure KEEP precision, retention among emitted TP findings,
advisory noise and actual CLI enforcement separately. KEEP-only enforcement is
now implemented. Approval still needs acceptable measured precision and validation
outside the development labels. Zero observed FP in one subgroup is
not a guarantee about new repositories.

## Historical detector reconciliation (before blocking wiring)

Status: **LOCAL CANDIDATE — HELD FOR ORIGINAL-SESSION POLICY REVIEW.** No PR or
publication. See [replay method and Muse comparison](../evals/release_088/README.md)
and [machine-readable aggregates](../evals/release_088/results.json).

The same 1,599 frozen input files were replayed through each source snapshot.
The available historical development labels cover 376 TP and 121 FP findings;
two other historical FP identities could not be transferred. Labels are
model-reviewed historical judgments, not independent human adjudication.

| Variant | Total delivered findings | Reference TP | Reference FP |
| --- | ---: | ---: | ---: |
| Canonical baseline, raw | 1,159 | 376 | 121 |
| Unmodified Muse, gate disabled | 1,094 | 369 | 111 |
| Unmodified Muse, default gate | 40 | 0 | 0 |
| Reconciled candidate, raw (or former annotation-only gate) | 972 | 376 | 106 |

Muse's 40 delivered findings are unlabeled. Its zero delivered reference FPs
therefore does not establish a useful precision result: all 369 remaining
reference TPs were also suppressed. An independent reviewer verified the exact
Muse source bytes, reaggregated the records, and reproduced the suppression of
one hash-verified labeled input. Malformed rule IDs, empty classifier context,
and path-extraction precedence are concrete integration defects. The candidate
retains Muse's model, scaler and threshold bytes unchanged.

The candidate removes 15 reference FPs through H4.5 fixes and preserves all 376
reference TPs by collision-checked rule/path/location/line/evidence identity.
Two diagnostic wordings changed without loss of the underlying warning.
Separately it removes 170 unlabeled H6 findings and two unlabeled references to
generated `dist/index.js` output, reviewed as non-actionable. These unknowns are
not relabeled as FP. The earlier “67 H6 FPs” and “greater than 25% FP reduction”
claims are not reproduced by this cohort.

| Candidate classifier bucket | Reference TP | Reference FP |
| --- | ---: | ---: |
| KEEP | 185 | 1 |
| ESCALATE | 178 | 59 |
| DISMISS | 13 | 46 |

KEEP has 99.46% observed precision and 49.20% reference TP recall here. It does
not achieve zero observed FP. At the existing `--fail-on review` severity
boundary, hypothetical KEEP-only blocking covers 184 TP and 1 FP; actual CLI
blocking still uses raw severity. These development measurements license a
**local-baseline comparison**, not population accuracy, calibration, or a
production default. The packet includes fixed threshold diagnostics without
refitting or selecting a winning threshold from these labels.

Engineering verification includes the full canonical suite, all 13 ported Muse
regression identities (the under-2500 assertion is explicitly revised to retain
a LOW notice), additional boundary and adversarial regressions, the evaluator's
own comparison checks, Ruff, clean fixture scan, isolated builds, metadata checks,
and wheel/sdist installs outside the checkout. Exact command logs and artifact
hashes are kept with the local verification receipt under `.hermes/local/`.

Remaining release decisions: select and independently validate the blocking
policy; decide whether to retain the LOW 1024-character notice; review the known
advisory false alarms. Do not enable classifier dismissal or claim default
production precision from this development cohort. PR submission remains held
by the owner's latest instruction.

## Expanded label review and blocking acceptance (before scoping fix)

All 490 previously unknown findings were reviewed twice without gate scores or
prior labels: 312 H5 and 178 H1.8. The reviewers agreed on 489 (488 FP, 1 TP);
one H5 disagreement remains unresolved. Both reviewers use the same Sol model
family. This is AI actionability review, not human ground truth. Combining these
with unchanged historical development labels mixes label provenance; independent
human adjudication and a held-out corpus remain necessary.

| Gate decision | TP | FP | Unresolved | Delivered behavior |
| --- | ---: | ---: | ---: | --- |
| KEEP | 186 | 482 | 1 | FAIL / blocks |
| ESCALATE | 178 | 66 | 0 | REVIEW / advisory |
| DISMISS | 13 | 46 | 0 | Hidden |
| Raw total | 377 | 594 | 1 | `--no-gate` |

The resolved KEEP precision is **27.84%** (186/668), with 72.16% false positives
among resolved blocking findings. Treating the unresolved item either way gives
27.80–27.95% precision. Visible output contains 548 FP, 364 TP and one unresolved
finding: **60.09% FP share** among resolved visible findings. This is a share of
emitted warnings, not the statistical false-positive rate over all negative input
opportunities. The gate retains 49.34% of labeled emitted TPs as blocking and
96.55% as visible; this does not measure recall of all real-world defects.

The earlier 99.46% was 185 TP / 186 labeled KEEP findings; it omitted 483 unknown
KEEP findings. It is not an overall precision result. Changing wiring alone does
not improve model accuracy. The >99% acceptance target **fails**.

An independent subscription Claude review recommended holding default-on approval
until representative precision is established. It is an AI reviewer, not an ESLint
maintainer. Four logged Jev calls reached stable choices under option reversal,
including holding approval for these measurements. Eighteen of twenty judgments
fell below the pilot's 0.75 confidence threshold, so they are advisory escalations,
not validation or authorization. No experimental dependency was added.

Current replay and verification receipts are linked from
[gate wiring evidence](../evals/gate_wiring/README.md). Historical Muse comparisons
above remain restricted to their shared historical labels; the 490 new labels
must not be projected onto unrelated Muse identities.
