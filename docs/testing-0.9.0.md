# Private 0.9.0 testing handoff

Repository: [hermes-labs-ai/lintlang-0-9-0](https://github.com/hermes-labs-ai/lintlang-0-9-0)
Branch: `codex/lintlang-088-release`. Package version: `0.9.0`.
Roli supplied GitHub as the testing environment; no VM host or separate image was
provided. Muse must have authenticated read access to the private repository.

## Clone and run

```sh
gh repo clone hermes-labs-ai/lintlang-0-9-0 -- --branch codex/lintlang-088-release
cd lintlang-0-9-0
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' build twine
.venv/bin/python -m lintlang --version
.venv/bin/python -m pytest -q
.venv/bin/ruff check src/ tests/
.venv/bin/python -m lintlang scan samples/clean_config.yaml --format json
```

The version command must report `lintlang 0.9.0`. Python 3.10–3.13 is the declared
CI matrix. The local validation interpreter and VM interpreter may differ.
No source, package, tests, or model call requires a provider API credential.

## Installed-consumer and integration compatibility

```sh
.venv/bin/python -m build --outdir .hermes/local/test-dist
.venv/bin/python -m twine check .hermes/local/test-dist/*
.venv/bin/python scripts/smoke_distributions.py .hermes/local/test-dist
.venv/bin/python -m pytest -q tests/test_megalinter_plugin.py tests/test_action_metadata.py tests/test_claude_code_plugin.py tests/test_gemini_extension.py tests/test_hermes_agent_integration.py tests/test_packaging_boundary.py
```

The artifact smoke installs wheel and sdist into separate clean environments,
runs `pip check`, verifies model/schema resources and the sole runtime dependency,
and exercises installed Python plus JSON/SARIF/GitLab CLI consumers. It verifies
CJK H1.8 KEEP blocking and English H1.8 exclusion.

MegaLinter tests validate its descriptor and CLI arguments in-process. They do
not establish current-version loading in a real MegaLinter container. Its 0.9.0
registry pin is a publication draft; testing an unpublished artifact in a
container requires installing the local wheel instead of fetching PyPI 0.9.0.

## Evaluations

Further Korean extraction was stopped at Roli's request. Saved source URLs:

- [38-repository collection](https://github.com/hermes-labs-ai/korean-skill-repos) (`repos.txt`)
- [Large skill registry](https://github.com/majiayu000/claude-skill-registry-data)

Partial source caches and extractor work remain in ignored local storage. They
are excluded from the private handoff and distributions; no new extraction count
is claimed.

The 972-finding historical cohort is private local data and is excluded from Git
and distributions. Its committed aggregate results are available; rerunning it
requires the owner's hash-verified manifest, source files, and label packet:

```sh
PYTHONPATH=src .venv/bin/python evals/gate_wiring/replay_current.py
PYTHONPATH=src .venv/bin/python evals/gate_wiring/mine_h18_languages.py
```

Private handoff is for review and testing. Public promotion requires Roli's review.

## Local verification before private handoff

- Full suite: 1,528 passed, 4 expected failures, 76 subtests passed.
- Ruff passed; the clean sample has zero findings.
- Wheel and sdist installed in separate clean Python 3.14 environments; dependency,
  bundled-resource, Python API, JSON/SARIF/GitLab, KEEP blocking, and English H1.8
  exclusion probes passed. Updated Twine validation accepted both distributions.
- Frozen replay: KEEP 179 TP / 10 FP, 94.71% observed development precision;
  all 249 eligible CJK H1.8 TP identities retained.

These are local results. The Python 3.10–3.13 CI matrix, Muse's own account, and a
real current-version MegaLinter container have not been executed here.
