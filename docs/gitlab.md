# GitLab Code Quality

Catch agent-configuration problems during code review. LintLang brings ambiguous
tool descriptions, mixed output formats, and missing constraints into
GitLab merge requests as Code Quality findings, with source locations, severity,
and suggested fixes.

## Add it to your pipeline

Copy the [LintLang CI job](../examples/gitlab-code-quality.yml) into your
`.gitlab-ci.yml`, then replace `AGENTS.md` with the files or directories you want
to check. The job installs LintLang 0.8.0 and runs on merge requests and the default
branch. Run the default-branch pipeline first so GitLab has a comparison report.

The example blocks on HIGH or CRITICAL findings and keeps the reports available
when the job fails. Change `--fail-on fail` to `--fail-on review` to include
MEDIUM findings, or remove the option for advisory checks. A full JSON report is
also available as a job artifact, including scores and scan coverage details.

To generate a report locally, run this from your repository root:

```bash
lintlang scan AGENTS.md --format gitlab --fail-on fail > gl-code-quality-report.json
```

Use the same input paths for your GitLab report and full JSON report. Choose
report destinations outside the scanned inputs; shell redirection overwrites
the destination before the scan starts.

## Read the findings

Each finding includes a rule code, description, suggested action, severity, and
repository-relative file location. Unchanged findings stay matched when unrelated
lines move, so merge requests highlight new and resolved issues.

LintLang maps its severities to GitLab's categories:

| LintLang | GitLab |
| --- | --- |
| CRITICAL | blocker |
| HIGH | critical |
| MEDIUM | major |
| LOW | minor |
| INFO | info |

A finding about specific text points to that text where its source line can be
resolved. A finding about a whole prompt, tool, schema, or message points to the
start of that construct. Multiline values that transform whitespace or escapes
may also point to the enclosing value.

Baselines and severity filters work as they do with other output formats. If an
input cannot be scanned or a finding cannot be assigned a valid source location,
the command fails with a diagnostic on standard error. The full JSON artifact
retains the scan details for troubleshooting.

The output follows [GitLab's Code Quality report format](https://docs.gitlab.com/ci/testing/code_quality/#code-quality-report-format).
GitLab receives the report through the CI job's `artifacts:reports:codequality`
setting; the local scanner does not upload files.
