# Contributing to LintLang

Focused fixes, reproducible false positives, disputed findings, and documentation
improvements are welcome. Read [AGENTS.md](AGENTS.md) for repository instructions
and [INTENT.md](INTENT.md) before changing product scope.

## Development setup

Use Python 3.10 or later. Fork the canonical
[hermes-labs-ai/lintlang repository](https://github.com/hermes-labs-ai/lintlang),
clone your fork, and create a focused branch from `main`. From the checkout root,
install the development dependencies into your chosen virtual environment:

```bash
python -m pip install -e ".[dev]"
lintlang --help
```

Keep dependencies and interpreter selection local to that environment. Public
Python functions need type annotations; modules use
`from __future__ import annotations`. Ruff configuration lives in
[pyproject.toml](pyproject.toml). Avoid repository-wide formatting or unrelated
cleanup in a focused change.

## Required checks

Run these from the repository root before opening a pull request:

```bash
pytest -q
ruff check src/ tests/
lintlang scan samples/clean_config.yaml
printf '%s' 'Is it true that X?' | lintlang preflight - --format json
bash evals/sample-detection-rate.sh
```

The designated clean sample must remain clean. The sample-detection script checks
four deliberately broken fixtures and one clean fixture; it is not an external
accuracy benchmark. The preflight example is advisory and should return `NOTICE`,
not a repository scan verdict.

Check packaging as described in [AGENTS.md](AGENTS.md). The `build` frontend is a
separate development tool, not a LintLang runtime dependency:

```bash
python -m pip install build
python -m build
```

This creates local distribution artifacts; it does not publish them. For a
pre-commit integration change, also exercise the hook used by CI:

```bash
pre-commit try-repo . lintlang --files AGENTS.md --verbose
```

CI tests Python 3.10 through 3.13 and checks the first-party Action on clean and
deliberately failing inputs. Optional local coverage is available with
`pytest --cov=lintlang --cov-report=term-missing`. Record any environmental or
pre-existing failure rather than suppressing it.

## Pull request expectations

Explain the problem, the bounded change, and the checks actually run. Keep
unrelated behavior, dependency changes, formatting, and release work out of the
patch. Include a minimal reproduction for a bug and identify any intentional
change to a public diagnostic, severity, extraction rule, or exit contract.

Documentation should follow its owning surface: the [README](README.md) provides
onboarding and navigation; focused guides explain tasks; the
[technical reference](llms-full.txt) owns exact behavior and limitations. When
moving documentation, migrate its consistency tests with the content. Do not
restore duplicated README material or remove a behavioral guarantee merely to
make a documentation test pass.

A documentation-only change should not alter scanner behavior. When verification
reveals an existing implementation bug, report it separately rather than silently
expanding the patch. Do not bump versions or publish a release as incidental
cleanup.

## Detector and extraction changes

Add positive cases and hard negatives that demonstrate the intended boundary,
including a minimal regression fixture for the reported issue. Update a sample
when the change is user-visible. Test unaffected cases, selected-pattern and
severity behavior, input errors, and relevant JSON/SARIF output. Preserve stable
finding identifiers unless the change explicitly requires a reviewed contract
migration.

For changes affecting baselines, test exact identity and occurrence-count limits;
suggestions must not become rule-wide suppressions. Keep HERM scores independent
of structural findings. Explain limitations in the reference instead of inferring
precision, recall, runtime safety, or provider compatibility from unit tests.

## Report a bug or false positive

Search [existing issues](https://github.com/hermes-labs-ai/lintlang/issues) first.
A useful false-positive report includes:

```text
LintLang version: (output of lintlang --version)
Command: (include paths, flags, filters, and baseline use)
Rule/finding ID: (the specific code, such as H1.6)
Minimal redacted reproduction: (input that still produces the finding)
Expected result:
Actual result: (verdict and relevant diagnostic)
```

Include the invocation directory when paths or baselines matter. Redact secrets,
personal data, and unrelated context before posting; verify that the reduced
input still reproduces the issue. Reports that dispute a finding's usefulness are
welcome even when the detector is behaving as implemented.

For vulnerabilities, follow [SECURITY.md](SECURITY.md), not a public issue. That
policy owns the reporting channel, supported versions, and response commitments.
