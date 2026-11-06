---
name: lintlang-release
description: Prepare, verify, publish, resume, or dry-run a LintLang release from merged main. Use for release readiness, version synchronization, release publication, or post-release closeout. This entrypoint selects one phase of the maintained release protocol and delegates mechanical work to the repository's existing scripts and workflow.
license: Apache-2.0
compatibility: Requires a LintLang repository checkout; public release steps also require normal GitHub and PyPI maintainer access.
---

# Release LintLang

This skill is a navigation entrypoint, not a second release system. Release only
changes already merged to `main`; do not pull in an unmerged feature, false-positive
experiment, classifier change, or another worktree merely because it is nearby.

## Select one phase

Read the [release protocol entry document](https://docs.google.com/document/d/1jac3QfhDxnnf9iMWNdLRw0ByL7HgNaUhJ-Jflq37t2Y/edit)
with an authorized connected Google Drive tool. Then read only the phase that
matches public state:

- [01 — Prepare & verify](https://docs.google.com/document/d/1tcXacj0cF07P4EJk1ii7gxvkonqd8eAHenwU7m5ef7g/edit): no verified GitHub/PyPI release yet.
- [02 — Publish & verify](https://docs.google.com/document/d/1K6E_3E8zitQOWJN5k67oFsb0OvEk-eIEyv-UmK9qBNc/edit): the candidate is verified and publication is next or in progress.
- [03 — Synchronize & close](https://docs.google.com/document/d/1RG3bG204R83X44OfpdspAy2ebFPru_I1PA_9kMKkWA4/edit): the GitHub release and PyPI distributions are independently verified.

Do not assume that a bare Drive URL is readable. If the connected document is
unavailable, the repository-local dry run below is still safe, but stop before a
public or cross-repository mutation and report the missing phase context. Treat an
old version number in the protocol as process context, never as a release fact.
Resolve the requested version and public state from the current checkout, GitHub
tag/release, and PyPI.

## Dry-run or prepare

Work in a clean branch or worktree from current `origin/main`. Let `VERSION` be the
explicit release version; use the version in `pyproject.toml` only for a no-change
current-state dry run.

```bash
python scripts/sync-version-docs.py --version "$VERSION" --check
```

Exit `0` means the controlled current-version surfaces are already synchronized.
Exit `1` lists the files that preparation would change; it is expected for a new
version. The command does not write. To prepare those mechanical changes, remove
`--check`, review the diff, then run the check again.

Create and review `.github/releases/v${VERSION}.md` for the requested release.
Derive its claims and contributor credits from the merged release diff and merged
pull requests. Credit external contributors by handle and contribution; do not
guess authorship. Keep historical and explicitly held pins unchanged.

After preparation, verify the existing contracts rather than inventing another
publisher:

```bash
python scripts/verify_release_tag.py --tag "v$VERSION"
python -m pytest -q tests/test_version_consistency.py tests/test_publish_workflow.py tests/test_systemic_automation.py
ruff check src/ tests/
python -m build
python -m twine check --strict dist/*
```

Run the repository's full required checks and independent review required by the
active phase before crossing its gate.

## Publish or close

`.github/workflows/publish.yml` is the only package release workflow. A pushed
`v*` tag starts publication; `workflow_dispatch` is recovery for an existing tag.
Do not create another release workflow, upload a separately built distribution, or
infer PyPI success from a green GitHub job. Follow Phase 02 and verify the actual
GitHub assets plus fresh installs from both the public wheel and sdist.

After publication, follow Phase 03. Re-run `sync-version-docs.py --check` for this
repository, classify current versus historical or held references before changing
them, use each controlled site's own update/deploy mechanism, and verify rendered
public surfaces. Record exact tag, commit, artifact hashes, checks, links,
contributors, and intentional exceptions in the normal PR/release trace.
