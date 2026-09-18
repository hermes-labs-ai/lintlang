# GitHub CI and Code Scanning

```bash
lintlang init --github --path AGENTS.md
```

Run this from your repository root to create
`.github/workflows/lintlang.yml`. Review the generated file before committing it.
The initializer writes configuration; it does not run a scan, commit a change,
enable Code Scanning, or upload a report itself.

## Prerequisites

Use an installed LintLang CLI with Python 3.10+, an existing Git repository, and
an instruction file or supported directory that is committed in that repository.
The initializer also works from a subdirectory: it finds the nearest `.git`
directory or worktree marker. Explicit `--path` values are interpreted from that
repository root, unlike ordinary `scan` paths, which are relative to the shell's
invocation directory.

GitHub Actions must be enabled for CI. Code Scanning upload additionally requires
an eligible repository with that feature enabled: public repositories on
GitHub.com, or eligible organization-owned private/internal repositories with
GitHub Code Security. See GitHub's
[SARIF upload prerequisites](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file).
Scanning and preserving a SARIF artifact do not themselves require a successful
Code Scanning ingestion.

## Generate and verify

Choose the actual input your agent reads:

```bash
lintlang init --github --path AGENTS.md
lintlang scan AGENTS.md --fail-on fail
git status --short
```

Open the generated YAML and review its input path, triggers, pins, failure
threshold, and upload permissions. A new workflow is untracked and will not
appear in an ordinary `git diff` until staged; use `git status` and inspect the
file directly. For subsequent tracked changes, use
`git diff -- .github/workflows/lintlang.yml`.

The generated workflow runs on pull requests and pushes to `main`. Change that
branch deliberately if your default branch differs. It uses immutable Action
commits, a read-only scan job, SARIF artifact preservation, and a separate upload
job. The current template pins the released LintLang v0.6.0 Action. This is a
reviewed released pin, not a request to install the newest package from PyPI;
it may intentionally trail a package version being prepared.

The complete maintained example is
[examples/github-code-scanning.yml](../examples/github-code-scanning.yml).
Use that example and the generated file rather than copying competing full
workflows from several guides. Inspect the authoritative
[Action inputs](../action.yml) when adapting a step.

### Automatic path detection

Without `--path`, the initializer chooses the first existing candidate in this
order: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
`.github/instructions`, `GEMINI.md`, `agent.yaml`, `agent.yml`, `agent.json`.
It selects one target; it does not combine all detected instruction surfaces.

Use `--path` when more than one candidate exists or when your repository uses a
different layout. The target must resolve to an existing file or directory
inside the repository. A missing target, an outside path, or no automatic
candidate causes a nonzero exit and no generated workflow. This existence check
does not establish that the target contains recognized instruction structures.
The Action's `path` input is one literal path, not a shell-expanded list. Use an
appropriate directory or separate scan steps for several independent targets.

### Idempotence and existing workflows

Re-running with the same generated content prints `Up to date` and returns 0
without changing it. A different existing `.github/workflows/lintlang.yml` is
left alone and causes a nonzero exit. Review or merge your customizations before
replacing it with `--force`:

```bash
lintlang init --github --path AGENTS.md --force
```

`--force` replaces that workflow's content; it does not merge custom jobs or
preserve edits. Other workflow files are not changed. Keep the old version in Git
so a deliberate replacement remains reviewable.

## Findings, thresholds, and input errors

| Invocation | Findings that make the command fail |
| --- | --- |
| CLI without `--fail-on` | None by verdict; findings are advisory |
| CLI `--fail-on fail` | HIGH or CRITICAL |
| CLI `--fail-on review` | MEDIUM, HIGH, or CRITICAL |
| First-party Action with omitted `fail-on` | HIGH or CRITICAL; its default is `fail` |

The Action always supplies its `fail-on` input to the CLI. For an advisory CI
scan, run the CLI without a verdict threshold rather than inventing an Action
value such as `none`. The legacy CLI `--fail-under` quality gate is separate;
see [exit behavior](../llms-full.txt#verdicts-and-exit-behavior).

Missing, unreadable, malformed, or otherwise uninspectable requested inputs stay
on the fatal `ERROR` channel, regardless of the verdict threshold. Another valid
input cannot mask such an error. Invalid command arguments are also nonzero.

An existing directory with no eligible files instead reports
`No matching files found to scan.` and exits 0, even with a verdict gate. This is
not an `ERROR`, but it is also not evidence that the intended instructions were
reviewed. Prefer an explicit known file when that presence matters.
`--write-baseline` is the exception: zero scanned files is an error and no baseline
is written.

## Existing-repository baselines

Create and review a baseline locally, then commit it and add
`baseline: .lintlang-baseline.json` to the Action's `with` inputs. Choose `fail`
or `review` for remaining findings. CI reads the baseline; it does not create or
refresh one. Follow [baseline adoption and lifecycle](baselines.md) for exact
matching, path roots, and review of backlog changes.

## Code scanning

To generate a report locally, run from the repository root and use a destination
different from the input and any baseline:

```bash
lintlang scan AGENTS.md --format sarif --fail-on fail > lintlang.sarif
```

SARIF is written to standard output; diagnostics and verdict-gate messages go to
standard error. A finding that trips the gate still leaves a report for review.
The report uses SARIF 2.1.0. Locations are repository-relative, URI-encoded paths;
inputs outside the reporting root are rejected rather than leaking absolute
paths. See the [SARIF reference](../llms-full.txt#json-and-sarif) for exact payload
and location limits.

The Action's optional `sarif-file` input generates a report but does not upload
it. It writes through a temporary file outside the scanned tree, preserves the
scanner's exit status, and rejects destinations that resolve to the input or
baseline, including symlink aliases. Output-write errors remain fatal.

The [canonical workflow](../examples/github-code-scanning.yml) separates two jobs:

- **Scan and preserve:** `contents: read`, checkout with
  `persist-credentials: false`, the pinned LintLang Action, then artifact upload
  under `if: always()`. The scan job still fails when the gate fails; artifact
  preservation is not `continue-on-error` for the scanner.
- **Upload:** waits for the scan job, downloads its artifact, and ingests SARIF
  using `github/codeql-action/upload-sarif`. This job has `actions: read`,
  `contents: read`, and `security-events: write`. Its fresh source checkout lets
  GitHub calculate fingerprints during ingestion; LintLang does not emit custom
  fingerprints or source snippets.

The upload job runs after a scan failure when its event condition permits it.
It skips fork pull requests and Dependabot pull requests; their scans and artifact
preservation still run. Do not work around those restrictions by executing
untrusted pull-request code under `pull_request_target` or broad write tokens.
Keep write permission out of the scan job.

A generated SARIF file is not proof of successful GitHub ingestion. Verify both
the workflow's scan outcome and the upload job, then inspect the repository's
Code Scanning results. LintLang findings are code-quality findings, not security
severity scores or a security certification.

## Troubleshooting and removal

**Initializer refuses an existing file:** review the tracked workflow and merge
changes manually, or intentionally use `--force`. It is protection against silent
replacement, not a failed scan.

**No automatic input or no eligible files:** choose an existing `--path`, confirm
that it is committed, and review directory exclusions and extraction coverage.
An unsupported vendor-specific structure can produce no covered findings; a
clean verdict is not proof that every structure was extracted.

**A gate fails:** distinguish `ERROR` from findings. Reproduce the same path,
version, filters, baseline, and threshold locally. Do not refresh a baseline or
add `continue-on-error` simply to turn the job green.

**Artifact missing:** inspect the scan and artifact-preservation steps first.
Installation failures may prevent report creation; the workflow deliberately
uses `if-no-files-found: error`. Check that producer and consumer use the same
artifact name and report path.

**Upload denied or unavailable:** check the event restriction, repository feature
eligibility, and upload-job permissions. A skipped fork upload is expected.
When only scanning/artifacts are desired, remove the separate upload job rather
than granting broader permissions or representing an absent upload as success.

To remove the generated integration, remove `.github/workflows/lintlang.yml` in a
reviewed change, or remove only its LintLang jobs from a workflow you have since
combined with other checks. Update any required-check configuration that referred
to those jobs. Leave unrelated workflows and repository instructions intact.

Related: [integrations](integrations.md), [baselines](baselines.md),
[technical reference](../llms-full.txt), [README](../README.md).
