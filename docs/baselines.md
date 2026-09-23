# Baselines: adopt now, review the backlog deliberately

A baseline is the reviewed starting set of findings already present when a
repository adopts LintLang. It records where the repository was at introduction,
acknowledges that existing backlog explicitly, and distinguishes new or changed
findings without treating the pre-existing backlog as newly introduced.

Use one when enabling a gate on an existing repository whose known findings
cannot all be resolved at once. It is not a rule-wide ignore or a declaration
that the acknowledged instructions are correct. The default scanner behavior is
unchanged until you pass `--baseline`.

**Availability:** baseline support is included in released LintLang 0.6.0 and
later. Install the release:

```bash
python -m pip install lintlang==0.7.1
```

## Create and review the starting set

Run from your project's Git root. Replace `AGENTS.md` with the actual file or
supported directory your team wants to gate:

```bash
lintlang scan AGENTS.md --write-baseline .lintlang-baseline.json
```

This prints the complete scan report and writes a new baseline. Review the
findings themselves before committing the file: confirm the intended scan scope,
identify false positives or accepted backlog, and decide what should instead be
fixed now. Hashes in the baseline are not a substitute for reading the report.

Creation is explicit. It never overwrites an existing path, including a symlink,
and writes nothing if any input fails or no input is scanned. A successfully
scanned file with zero findings can produce a valid empty baseline; scanning zero
files cannot. The destination's parent directory must already exist. Omit
`--fail-on` and `--fail-under` for the initial inventory: those gates can make a
completed inventory return nonzero because of findings or quality scores.

## Apply it locally

After review, commit the baseline with the gate configuration:

```bash
lintlang scan AGENTS.md --baseline .lintlang-baseline.json --fail-on review
```

`--fail-on review` blocks remaining MEDIUM, HIGH, or CRITICAL findings.
`--fail-on fail` blocks remaining HIGH or CRITICAL findings. An unchanged scan
with all findings acknowledged passes either structural gate. A newly added
file receives no allowance from another file's entries.

Use the same scan paths, `--patterns`, `--min-severity`, and directory exclusions
when creating and applying a baseline. Filters run before baseline matching.
Expanding the selected rules or severity range can reveal findings that were
never acknowledged. Directory scans exclude the active baseline file itself;
this does not exclude every JSON report or historical baseline in that directory.

## Apply it in GitHub CI

Add the optional `baseline` input to your existing LintLang Action step:

```yaml
- uses: hermes-labs-ai/lintlang@175a9a19414aff9a1752d3b9850d6cf58d59fb32 # v0.7.0
  with:
    path: AGENTS.md
    baseline: .lintlang-baseline.json
    fail-on: review
```

The Action installs the scanner from its own checked-out source. For the complete
workflow, immutable pins, and permissions, use the [GitHub guide](github.md)
rather than maintaining another workflow here.

The same input works with `sarif-file`. Only remaining findings are emitted as
SARIF results; the run's `properties.lintlangBaseline` contains the suppressed
count and verdict scope. The Action rejects a SARIF destination that resolves
to the baseline, including symlink aliases. See
[Code Scanning permission and upload guidance](github.md#code-scanning).

CI only reads the committed baseline. It never creates or updates one. Review
baseline edits as carefully as changes to the CI gate itself: anyone who can
change the baseline can acknowledge findings.

## Exact, count-limited matching

Each entry identifies a repository-relative POSIX path, a SHA-256 finding
fingerprint, and an occurrence count. The fingerprint includes the diagnostic
code, severity, diagnostic location, description, and evidence. Matching is
exact: there are no wildcards or rule-wide exemptions.

A changed code, severity, location, message, or evidence can reopen a finding,
including after a detector upgrade. Suggestions, the rule's display name, and
the separate source-region field are not identity. Python source-path prefixes
in diagnostic locations are normalized to the repository-relative path; line
information encoded in the location remains part of the identity.

Additional occurrences beyond the recorded count remain visible. Repeating the
same file through multiple CLI paths does not enlarge its allowance. HERM
scores, quality thresholds, and source input errors are unchanged. Terminal and
Markdown reports state that their verdict covers remaining findings; JSON adds
`baseline.suppressed` to each scanned result.

### Paths and invocation roots

Inside a Git worktree, matching uses the nearest repository root. In a non-Git
directory, the invocation directory is the root. Source paths are resolved before
matching; inputs outside that root are rejected, including symlink escapes.

The `--baseline` filename and ordinary scan arguments are resolved from the
invocation directory, not automatically from the Git root. Run from the same
project root locally and in CI so both the selected files and baseline path are
unambiguous. Absolute versus relative Python invocation paths do not by themselves
change a normalized fingerprint; moving or renaming the source can.

### Invalid inputs and privacy

Missing, malformed, or unsupported baseline inputs and failed baseline writes
return nonzero even without a severity gate. The loader rejects unknown fields
and schema versions, duplicate entries or JSON keys, noncanonical paths, invalid
hashes, and invalid counts. Source input errors also remain nonzero and cannot
be acknowledged away. See the exact schema in the [technical reference](../llms-full.txt).

The baseline stores paths and hashes, not raw prompts or finding evidence.
Hashes are not encryption: review filenames and the sensitivity of your inputs
before publishing a baseline. Ordinary scan reports may still contain evidence.

## Refresh and shrink the backlog

After fixing findings, create a candidate at a new path and review it before
replacing the committed baseline:

```bash
lintlang scan AGENTS.md --write-baseline .lintlang-baseline.candidate.json
git diff --no-index .lintlang-baseline.json .lintlang-baseline.candidate.json
# After review:
mv .lintlang-baseline.candidate.json .lintlang-baseline.json
```

`git diff --no-index` exits 1 when the files differ; that is expected. Compare
the complete scan report as well as the hash changes. Check that removed entries
represent resolved or intentionally out-of-scope findings, and review any new
allowances explicitly. Never refresh automatically after a failed gate: doing
so can accept the very changes the gate was meant to surface.

Unused entries are allowed, so removing a finding does not itself break CI.
Prune them through the reviewed refresh above. An identical finding reintroduced
at the same identity can still match an old entry until it is removed. A baseline
records acknowledged identities, not the history of when each defect was fixed.
It does not assess runtime behavior or establish safety.

Related: [GitHub CI](github.md), [integrations](integrations.md),
[technical reference](../llms-full.txt), [README](../README.md).
