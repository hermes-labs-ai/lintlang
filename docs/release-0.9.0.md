# LintLang 0.9.0 — private review draft

Status: **unpublished private testing candidate**. Roli reviews before any public
push, tag, merge, GitHub release, or PyPI publication. The branch remains
`codex/lintlang-088-release`; its package version is 0.9.0.

LintLang checks agent configuration, tool interfaces, and skill selection text
before runtime. Scans are local and deterministic, make zero model calls, and
retain PyYAML as the only runtime dependency. JSON, SARIF, and GitLab outputs
support existing automation consumers.

## Current development evidence

The full replay checks **1,599 hash-verified source files** against all **972
original finding labels**. KEEP contains **179 TP / 10 FP: 94.71% observed
precision**. Visible KEEP + ESCALATE output contains 341 TP / 33 FP; its labeled
FP share is 8.82%. DISMISS hides 12 TP / 19 FP. These are development-cohort
counts with mixed historical and AI-review labels, not independent held-out
accuracy or recall over all possible defects. This does not establish the
earlier >99% blocking-precision target.

H1.8 runs only for Chinese, Japanese, and Korean descriptions. It retains
**249/249 eligible TP identities** from all 272 original H1.8 TPs; the other
23 are explicitly excluded by language. All retained gate decisions and scores
match the frozen receipt; labels, model weights, and thresholds are unchanged.

| Language | All labeled TP retained | KEEP FP before → after | All labeled FP before → after |
| --- | ---: | ---: | ---: |
| Chinese | 96/96 | 19 → 2 | 82 → 19 |
| Japanese | 141/141 | 43 → 7 | 67 → 14 |
| Korean | 12/12 | 1 → 1 | 3 → 1 |

The eligible KEEP-only H1.8 FP set falls **63 → 10 (84.1% fewer)**, with 120/120
KEEP TPs retained. The full labeled CJK FP set falls 152 → 34. Excluded English,
Spanish, and Turkish descriptions produce no H1.8 finding and are not counted as
FPs or TPs. Their modules remain research-only.

Further Korean source extraction is parked at the owner's request. The source
collection and large registry URLs are saved in [testing notes](testing-0.9.0.md).
No additional corpus result is claimed.

Machine-readable evidence:

- [Full current replay](../evals/gate_wiring/current-results.json)
- [H1.8 language replay](../evals/gate_wiring/h18-language-results.json)

## Migration and compatibility

- The learned gate is enabled by default. Selected KEEP findings block with
  FAIL/exit 1; ESCALATE remains advisory; DISMISS is hidden with diagnostic counts.
  `--no-gate` and Python `gate=False` restore raw detector behavior.
- H1.8 now skips languages outside zh/ja/ko. Other skill metadata checks still run.
- H5 and explicit H5 selection are removed; `detect_h5` imports are unsupported.
  H6 scanning is retired; the legacy `detect_h6` import remains a no-op.
- H1.1 no longer reports empty descriptions. H1.7 length tiers, H1.9 name handling,
  H4 occurrence handling, and exact test/fixture/teaching directory exclusions
  follow the reconciled candidate. Explicit-file scans remain available.
- The English trigger regex and gate model/scaler/threshold bytes are unchanged.
  A Chinese exclusion followed by a contrasting positive clause in the same
  sentence remains a known minor H1.8 edge case under the frozen mappings.

Consumers relying on retired rules or previous default exit behavior must review
these changes. Passing integration checks does not promise compatibility with
every downstream environment. Registry-pinned 0.9.0 commands become usable only
after publication; use the private source checkout or built artifacts for testing.

## Private testing

See [Muse testing instructions](testing-0.9.0.md) for installation, corpus replay,
integration contracts, and isolated wheel/sdist probes. No separate VM host or
testing image was provided; the testing handoff is the private Hermes Labs GitHub
repository. A local clone check establishes repository readability here, not
Muse's account permissions or successful execution on an unobserved VM.

[Earlier 0.8.8 reconciliation](release-0.8.8.md) remains historical. Its pre-H5,
pre-language-scope precision figures are superseded by the current replay above.
