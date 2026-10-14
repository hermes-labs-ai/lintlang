# H1.8 comparison after H5 removal

The frozen 972-finding corpus does **not** contain the requested 150-TP subgroup:
it has 272 historical H1.8 TP labels, of which 126 are KEEP. The 172 KEEP FP
labels comprise 171 from the expanded review and one historical FP. The original
manifest pins `eval-seed-v3.jsonl` by SHA-256
`a08029d7cbefe5d3cb7502d7ee6743a37205605e638555261614afb50a725d1f`;
the current files named seed-v1 and seed-v2 have different labels and hashes.
No labels were changed for this comparison.

The evidence shows a **length/severity and review-provenance split, not two
established semantic defect types**. All 272 historical TP descriptions have
20–119 Unicode code points (median 60); the 126 KEEP TPs have median 54.5.
Of the 172 KEEP FPs, 171 have at least 120 code points (median 152, range
106–683). That boundary is exactly H1.8's MEDIUM-versus-LOW severity cutoff.
Both KEEP groups are entirely Markdown skill descriptions and overwhelmingly
come from the same repository, ECC (125/126 TP and 159/172 FP), often its
translated `docs/*/skills/*/SKILL.md` copies; they are not tests versus production
or different file formats. There are 37 skill directory names in both KEEP
label groups. Both short and long descriptions often name a concrete task,
and translated equivalents receive opposite labels. The expanded rubric accepts
an inferable task/domain as sufficient selection guidance and explicitly rejects
a requirement for literal English trigger words. Existing TP labels were
transferred unchanged under a different review process. Several look questionable
under that rubric; short text is not evidence of inadequacy. All these descriptions
miss the detector's finite trigger vocabulary, including an FP that explicitly
states a trigger in Japanese. A clean semantic separation is therefore unproven;
H1.8 needs consistent adjudication before a fix can be justified.

## Concrete examples (labels retained, not independently certified)

All paths below are relative to the frozen `affaan-m/ECC` checkout. Character
counts use complete parsed front matter, not the diagnostic's 120-character
truncated evidence. English renderings below are interpretations of the source.

| Label | Source | Characters | Description / meaning |
| --- | --- | ---: | --- |
| TP, KEEP | `docs/zh-CN/skills/golang-testing/SKILL.md` | 54 | Go testing patterns: table-driven tests, subtests, benchmarks, fuzzing, coverage and idiomatic TDD. This already identifies a concrete task. |
| TP, KEEP | `docs/ja-JP/skills/python-testing/SKILL.md` | 55 | Python testing strategies using pytest, TDD, fixtures, mocks, parameterization and coverage. |
| TP, KEEP | `docs/tr/skills/verification-loop/SKILL.md` | 55 | “Claude Code oturumları için kapsamlı doğrulama sistemi.” A comprehensive verification system for Claude Code sessions; less specific than the testing examples. |
| FP, KEEP | `docs/zh-TW/skills/golang-testing/SKILL.md` | 152 | English description of the same Go testing techniques and TDD as the TP above. Folder locale does not necessarily identify the content's language. |
| FP, KEEP | `docs/tr/skills/python-testing/SKILL.md` | 127 | Turkish description of the same pytest/TDD/fixtures/mocks/parameterization/coverage techniques as the TP above. |
| FP, KEEP | `docs/ja-JP/skills/quarkus-tdd/SKILL.md` | 106 | Quarkus 3.x TDD with named testing tools; explicitly says to use it when adding features, fixing bugs or refactoring event-driven services. The detector misses the Japanese trigger. |

Full descriptions, finding IDs, aggregates and input/source digests are in
[h18-analysis.json](h18-analysis.json). Reproduce with
`PYTHONPATH=src python evals/gate_wiring/analyze_h18.py` using the private corpus.
This analysis does not change H1.8, labels, gate weights or thresholds.

## H5 removal and replay

The detector function, H5-only helper/constants and registry entry are removed.
Other detector functions are AST-identical to the pre-removal snapshot, and
`detectors/h1.py` is byte-identical. Explicit H5 selection is invalid; historical
serialized H5 findings remain readable.

`PYTHONPATH=src python evals/gate_wiring/scoping_replay.py --retired-h5`
replays all 1,599 hash-verified source files with unchanged labels and gate
parameters. [h5-removal-results.json](h5-removal-results.json) records 660 raw
findings. KEEP is **185 TP / 172 FP = 51.82% precision**; all remaining KEEP
FPs are H1.8. Visible output is **363 TP / 238 FP = 39.60% FP share**.
H5 retirement removes 310 FP, one historically labeled TP and one unresolved
finding from the explicit-file cohort (309 FP after the earlier scope exclusion).
This is intentional rule retirement, not a claim of zero TP loss.

Validation: **1,185 tests passed**, 4 expected failures and 76 subtests. Obsolete
H5-only tests were removed; consumer tests now use active H2/H4/H1.8 fixtures.
Ruff, the clean sample and all five bundled sample outcomes passed.

Local work only. No push, PR, merge, tag or publication is authorized before review.
