# GitLab Code Quality

LintLang can write a GitLab Code Quality report directly. From the repository
root, scan the instruction files your agents actually read:

```bash
lintlang scan AGENTS.md --format gitlab --fail-on fail > gl-code-quality-report.json
```

The maintained [CI job](../examples/gitlab-code-quality.yml) installs the
v0.8.0 package, runs on merge requests and the default branch, and publishes
`gl-code-quality-report.json` through `artifacts:reports:codequality`. The
default-branch pipeline provides the comparison report for merge requests. Copy
the job into `.gitlab-ci.yml` and replace `AGENTS.md` with your actual input or
list of inputs. The example also stores a full JSON report with verdicts,
coverage notes, and HERM data. It retains the scan's failure status and uploads
both files even when the gate fails.

The report is one JSON array, including when there are no reportable findings.
Each entry has `description`, `check_name`, `fingerprint`, `severity`, and a
`location` with a repository-relative `path` and positive integer
`lines.begin`. Paths do not start with `./`. LintLang maps CRITICAL to GitLab
`blocker`, HIGH to `critical`, MEDIUM to `major`, LOW to `minor`, and INFO to
`info`. Fingerprints are deterministic across scan order and preceding line
shifts; identical repeated findings in a file receive distinct fingerprints
in source order. Changing a finding's code, logical location, description, or
relative file path changes its fingerprint.

Locations come from source evidence. For prompt text, LintLang uses an exact
text offset when it can map that offset safely to a physical line. Whole-prompt
findings point to the actual prompt construct. Structured YAML/JSON findings
use the parsed scalar, message, schema, or tool construct that produced them;
when a decoded scalar cannot be mapped to a precise content line, its real
source start line is used. LintLang does not assign an arbitrary first line of
the file.

If an unexpected or programmatically supplied finding still has no supported
source line, GitLab cannot represent it. LintLang omits it from the Code Quality
array, prints the omitted count to standard error, and exits nonzero even in
advisory mode. Inspect the full JSON report or `--format sarif` for that finding.
Baselines and severity filters apply before reporting, just as for other output
formats. Input, baseline, and outside-root path errors return a nonzero status;
the report remains a valid JSON array, and diagnostics go to standard error.
GitLab Code Quality carries structural findings, not HERM scores or coverage
notes.

Write the report to a path outside the scanned inputs. Shell redirection opens
the destination before LintLang starts and can truncate an input if they share
a path. This report is generated locally; LintLang does not upload it itself.
See [GitLab's report format](https://docs.gitlab.com/ci/testing/code_quality/#code-quality-report-format)
for the receiving contract.
