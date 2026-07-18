# Provider-neutral preflight (unreleased candidate)

`lintlang preflight` examines one instruction plus explicit caller-supplied
context before a host sends that instruction to an agent. It is deterministic,
local, and provider-neutral. It does not call a model, retrieve user history,
decide whether a claim is true, silently rewrite text, or send anything.

The repository-oriented `lintlang scan` command and its `ERROR | PASS | REVIEW | FAIL`
verdicts remain unchanged. Preflight is a separate surface with five explicit
states:

| State | Meaning | Exit |
|---|---|---:|
| `ALLOW` | Required coverage completed and no listed risk was detected | 0 |
| `NOTICE` | Reviewable input risk or reversible suggestion | 0 |
| `HOLD` | Exact missing requirement or mechanical conflict | 1 |
| `ERROR` | Invalid input or context; analysis did not run | 2 |
| `UNAVAILABLE` | Required coverage could not safely complete | 3 |

`ALLOW` is not a truth, safety, quality, or provider-compatibility guarantee.

## 90-second proof

An accidentally leading truth question receives an advisory finding and an
explicitly requested patch preview:

```console
$ printf '%s' 'Is it true that remote work always reduces productivity?' \
    | lintlang preflight - --include-snippets
NOTICE
PF001 validation-seeking-frame [0:15] pf_...
  Risk: The wording frames confirmation as the conversational default.
Correction pc_... (meaning preservation unverified)
--- prompt
+++ prompt
@@ ...
-Is it true that remote work always reduces productivity?
+What evidence supports or refutes whether remote work always reduces productivity?
```

The matched neutral control remains clean:

```console
$ printf '%s' 'What evidence supports or refutes whether remote work always reduces productivity?' \
    | lintlang preflight -
ALLOW
```

Preflight does not guess missing preferences or providers. A host can supply
explicit context from the user, a repository, or a separate system such as
Hermeneutic:

```console
$ printf '%s' 'Make a video about alligators.' \
    | lintlang preflight - --context examples/preflight/video-context.json --format json
```

That example returns `NOTICE` with a source-hash-bound correction because the
known `IN_PROMPT` binding has not yet been materialized. Removing the binding
while retaining its required declaration returns `HOLD`; it never invents
Gemini, a house format, or another missing value.

## Privacy and corrections

Default terminal and JSON output contain hashes, identifiers, spans, bounded
explanations, and replacement/diff hashes. They do not contain raw prompt,
context, snippets, replacement text, or unified diffs.

`--include-snippets` is the explicit local disclosure switch for evidence and
patch previews. `--apply CORRECTION_ID` is a separate explicit operation: it
checks the exact source hash, applies one correction in memory, re-runs preflight
once with the same context and policy, and writes corrected text to standard
output. It never edits the input file or contacts a provider.

## Context JSON

Context is data, not an instruction channel:

```json
{
  "requirements": [
    {
      "key": "video_format",
      "required": true,
      "description": "The user-approved house video format"
    }
  ],
  "bindings": [
    {
      "key": "video_format",
      "value": "16:9, 20 seconds, title card then three scenes",
      "source": "user",
      "delivery": "IN_PROMPT"
    }
  ],
  "constraints": []
}
```

`SIDE_CHANNEL` means the host promises to deliver the binding through its own
provider-specific context mechanism. `IN_PROMPT` means the value must appear in
the outgoing instruction. LintLang performs neither delivery.

Typed constraints use objects, for example:

```json
{"kind": "output_format", "value": "markdown"}
```

Only `json` and `markdown` are recognized output formats in rule bundle v1.

## Initial input-risk rules

- `PF001` validation-seeking frame — heuristic, `NOTICE` only.
- `PF002` presupposed causality — heuristic, `NOTICE` only.
- `PF003` unresolved context reference — deterministic phrase-to-binding lookup,
  `NOTICE` only.
- `PF004` missing required context — exact missing value can `HOLD`; a known
  `IN_PROMPT` value produces `NOTICE` plus a reversible insertion.
- `PF005` explicit instruction conflict — exact typed-format or mechanical
  structural conflicts can `HOLD`.

These are derived input-risk labels. They are not claims that a model exhibited
one of the seven output behavior modes described in Hermes Labs' published
research.

## Python API

```python
from lintlang import PreflightRequest, preflight_text

result = preflight_text(PreflightRequest(
    prompt="Is it true that remote work always reduces productivity?",
))

print(result.status.value)  # NOTICE
print(result.to_json())     # raw text redacted by default
```

When selected rules are required, unsupported declared languages and unsafe,
unbalanced quote/code scope return `UNAVAILABLE`, never `ALLOW`. A policy with
no enabled rules skips rule and scope analysis and reports every component as
`NOT_REQUIRED`. Enabled-but-optional rules report unavailable analysis as
`NONE` coverage plus a warning without claiming that required coverage failed.
Empty, oversized, malformed, or ambiguous inputs return `ERROR`.
