# Adopting a gate with a baseline

## What real job this models

A project wants to gate merges on lintlang but already has findings it cannot fix in one change. It records the reviewed backlog in a baseline file and gates on anything new. This example runs that flow on a 15-tool MCP manifest with 18 existing MEDIUM findings (undescribed parameters, rule H3).

```bash
lintlang scan input.json --fail-on review                                  # exit 1: 18 MEDIUM
lintlang scan input.json --write-baseline .lintlang-baseline.json          # exit 0: writes the baseline
lintlang scan input.json --baseline .lintlang-baseline.json --fail-on review   # exit 0: PASS, 0 findings
```

See [expected-output.txt](expected-output.txt) for the output of all three steps. The baseline records a fingerprint and a count per finding and does not turn a rule off. Read the report before committing the baseline; the baseline is an acknowledgement, not a review. The full baseline guide is [docs/baselines.md](../../../docs/baselines.md).

## Provenance

- Repository: <https://github.com/julymetodiev/post-cortex> (MIT)
- Commit: `da4b511dfc1322ff16256515afa5167b67f98499`
- File: `tools.json`, copied unchanged as `input.json`
- sha256: `48a6434dbfe98eb10428e2b45a57030f924c29aa1d107ff3be6ec59b4bab36a1`

License text and notice: [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md). The baseline file is written by the test into a scratch copy and is not committed.

## What this does not tell you

- The final `PASS — 0 findings` does not show how many findings the baseline suppressed. The count appears only when the baseline is written (`18 finding(s)`).
- Paths are part of the identity. Run the create and apply steps from the same directory with the same path, or the findings will not match and the gate will trip again.
- This example does not show a new finding arriving. A baseline covers exact fingerprints and counts, so a changed or added finding is not covered; that behavior is tested in the repository's baseline tests, not demonstrated here.
- Undescribed parameters are a schema-quality signal. They do not show the tools misbehave.
