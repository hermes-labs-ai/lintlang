# LintLang 0.9.0

**Catch agent failures before your agent runs.**

LintLang is a static linter for AI agent configs, tool descriptions, and system
prompts with zero-LLM CI gating. It is local and deterministic, makes zero
model calls, and keeps PyYAML as its only runtime dependency. JSON, SARIF, and
GitLab outputs support existing automation consumers.

Status: **staged release candidate — not published.** No merge, tag, GitHub
release, or PyPI publication has occurred. The release branch is
`codex/lintlang-088-release`; the package version is 0.9.0 everywhere
(`pyproject.toml`, `src/lintlang/__init__.py`, integration manifests).

## Caveats and limits — read first

- **KEEP precision is 94.71%, below the 95% bar.** On the frozen development
  cohort, KEEP holds 179 TP / 10 FP. All 10 false positives are H1.8.
- **The cohort is ECC-biased: 176 of the 179 KEEP TPs come from a single
  repository.** The diverse-validation hold stands — nothing here establishes
  precision on a diverse repo population.
- **Frozen development-cohort results, not held-out accuracy.** 1,599
  hash-verified source files checked against 972 original finding labels with
  mixed historical and AI-review labels. Visible KEEP + ESCALATE output is
  341 TP / 33 FP (8.82% labeled FP share); DISMISS hides 12 TP / 19 FP. This
  does not establish the earlier >99% blocking-precision target.
- **P2 kwarg/callee integration is deferred.** The supplied patches require a
  different extractor baseline and do not apply to this candidate. Taint
  tracking remains out of scope.
- **P1/P2 pipeline detectors are heuristics.** P1 flags thresholds without
  calibration comments; P2 flags long prompts embedded in Python source on
  length alone (LOW/INFO severity). Neither is covered by the precision
  figures above.

## What changed

- **H1.8 scoped to Chinese, Japanese, and Korean descriptions.** Other language
  maps are retained for research only. Eligible KEEP H1.8 false positives fell
  63 → 10 (84.1% fewer) while all 249/249 eligible TP identities were retained
  (Chinese 96/96, Japanese 141/141, Korean 12/12). A Chinese exclusion followed
  by a contrasting positive clause in the same sentence remains a known minor
  H1.8 edge case under the frozen mappings.
- **H5 implicit-instruction detection removed.** Explicit H5 selection and
  `detect_h5` imports are no longer supported.
- **H6 retired from scanning.** The historical `detect_h6` import remains a
  no-op for compatibility.
- **H1.1 retired for empty tool and skill descriptions.** Empty descriptions no
  longer fall through to H1.2.
- **Offline learned gate enabled by default.** Selected KEEP findings block
  (FAIL / exit 1); ESCALATE remains advisory; DISMISS is hidden with
  diagnostic counts. `--no-gate` / `gate=False` restore raw detector behavior.
  The gate fails closed with raw findings retained when model artifacts are
  unavailable.
- **MegaLinter severity blocking preserved** in the 0.9.0 integration.
- Exact test, fixture, and teaching directory components are skipped during
  directory scans and discovery; explicitly named files remain inspectable.

## Migration and compatibility

- Consumers relying on retired rules (H5, H6, H1.1-empty) or on the previous
  default exit behavior must review these changes.
- H1.8 no longer reports for descriptions outside zh/ja/ko; other skill
  metadata checks still run.
- Registry-pinned 0.9.0 install commands become usable only after publication;
  use the source checkout or built artifacts for testing until then.
- Passing integration checks does not promise compatibility with every
  downstream environment.

## Verification

- Full suite: **1,525 passed, 3 skipped, 4 xfailed (strict, documented
  limitations), 76 subtests passed** — zero failures. `ruff check src/ tests/`
  clean.
- Default-gate replay over the frozen corpus: PASS_REPLAY; the committed
  aggregate receipt (`evals/gate_wiring/current-results.json`) is arithmetically
  consistent (179 TP / 10 FP = 94.7090%). The private frozen corpus is excluded
  from git by design; replay re-execution requires the review packet under
  `.hermes/local/`.
- Machine-readable evidence: `evals/gate_wiring/current-results.json`,
  `evals/gate_wiring/h18-language-results.json`, `docs/release-0.9.0.md`.

## Semver note

0.9.0 (not 0.8.x): this release removes rules (H5, H6, H1.1-empty) and
materially changes multilingual detection behavior (H1.8 CJK scoping) plus the
default gate behavior. That is a minor-version change, not a patch.
