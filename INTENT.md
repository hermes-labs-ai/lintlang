# LintLang: product intent

## Why LintLang exists

Agent instructions increasingly function as executable infrastructure: they
shape tool selection, operational limits, output contracts, and how work is
handed between components. Yet they often receive less static scrutiny than
ordinary source code. A file can parse successfully while leaving those
instructions ambiguous, unbounded, or internally inconsistent.

LintLang exists to make a bounded class of these defects inspectable before
runtime. It gives an author or reviewer evidence to examine while instructions
are being written and changed, rather than requiring a model execution to
surface every reviewable problem.

## The intervention

The primary product is deterministic static analysis of repository artifacts:
recognized tool/configuration structures, prompts and instruction files, and
supported extractable Python prompt-pipeline patterns. Findings identify the
rule, severity, location, evidence, and suggested review action where supported.

Static analysis is useful here because it is local, repeatable, inspectable, and
compatible with ordinary review and CI workflows. It has a narrower evidence
boundary than a model-based evaluator. LintLang makes no LLM calls, retrieves no
remote rules, and sends no telemetry or network requests during a scan. Package
installation and a host integration's own provider activity are separate from
that scanner contract.

This direction grew from Hermes Labs' work on epistemic failure modes. The
[research lineage](docs/research.md) explains the adaptation from behavioral
research into engineering checks without treating provenance as validation.

## Design principles

- **Evidence before authority.** A finding is a reason to inspect a particular
  artifact, not an assertion that arbitrary prose is wrong or that a model will
  fail. Stable diagnostic identifiers and explicit limitations make findings
  discussable and reproducible.
- **Deterministic, local analysis.** For the same recognized inputs, configuration,
  and rule version, findings and verdicts must be repeatable without an LLM
  dependency. A scan should fit local development as well as CI.
- **Bounded and composable claims.** Static checks complement syntax/schema
  validation, runtime evaluation, and domain/security review. A clean scan does
  not establish safety or correctness; it only reports what selected checks
  found in recognized content.

## Scope and non-goals

LintLang is intended to inspect language-bearing artifacts that authors can
review before execution. Supported formats and extraction limits belong in the
[technical reference](llms-full.txt), not in an implied promise to understand
every configuration accepted by every agent host.

It does not evaluate runtime model behavior, verify truth, prove semantic
correctness of arbitrary prose, certify safety, guarantee provider compatibility,
or replace domain judgment. It does not infer that a research failure mode
occurred simply because a related input pattern was found. The absence of a
finding is not evidence that an unsupported structure was analyzed.

## Product boundary

Repository scanning is the primary static-analysis product. Preflight is a
separate bounded capability for one present instruction and explicit
caller-supplied context. It does not retrieve personal history, silently rewrite
files, or send instructions to a provider. Its states, context contracts,
correction protocol, and enforcement limits are documented in
[the preflight guide](docs/preflight.md) and [technical reference](llms-full.txt#preflight).
Those mechanics must not redefine repository scan verdicts.

## Durable engineering invariants

- Keep the scanner deterministic and free of model or network dependencies.
  `pyyaml` is the sole runtime dependency; adding another requires a deliberate
  minor-version change and a changelog entry explaining why.
- Keep HERM dimensional scoring separate from structural findings. Detectors do
  not modify HERM scores. Parity claims require a checked-in comparison corpus
  and executable gate, not a shared name or a clean sample.
- Preserve explicit error and enforcement boundaries. Input errors cannot be
  hidden by severity gates or baselines. Preflight heuristics remain notice-only;
  only typed missing requirements or mechanical conflicts may hold. Default
  preflight serialization omits raw prompt, context, replacement, and diff text.
- Bind detector changes to positive fixtures and hard negatives for the intended
  boundary. Bundled sample checks are regression evidence, not detector-accuracy
  estimates or proof of production readiness.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and required checks,
and [README.md](README.md) for onboarding and navigation.
