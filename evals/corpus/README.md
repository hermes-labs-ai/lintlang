# LintLang regression corpus

`cases.jsonl` is the source of truth for small, public-safe detector regressions.
Tests consume cases directly; project notes elsewhere, including Notion, are
projections rather than an alternate corpus.

Each JSON line is one case. Keep `case_id` immutable, give every phrase class a
positive or negative control, and link the case to a focused test. Store only
sanitized text: never include private prompts, credentials, user data, or local
transcript paths. Tests should assert the intended signal or finding boundary,
not an entire score that can change for unrelated reasons.

A single case demonstrates a reproducible boundary, not prevalence or broad
detector calibration. Add broader evaluation evidence before making either
claim.
