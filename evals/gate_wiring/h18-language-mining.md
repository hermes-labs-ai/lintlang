# H1.8 language trigger mining

Frozen 972-finding development corpus; only the 172 FP / 126 TP KEEP cohort is mined and replayed. Historical/transferred and AI-review labels are preserved, not independently certified. Mining and evaluation use the same descriptions; this is a development replay, not held-out accuracy.

Actual scanner replay: FP **172 → 106** (66 removed, 38.37% reduction); TP **126 → 126** (100.00% retention).

| Description language | FP before | FP after | TP before | TP after |
| --- | ---: | ---: | ---: | ---: |
| en | 54 | 43 | 3 | 3 |
| es | 37 | 37 | 0 | 0 |
| ja | 43 | 10 | 80 | 80 |
| ko | 1 | 1 | 7 | 7 |
| tr | 18 | 13 | 3 | 3 |
| zh | 19 | 2 | 33 | 33 |

Language tags come from content: kana → ja, Hangul → ko, Han → zh; Turkish spelling/ASCII cues handle Latin text. Spanish is tagged for completeness. Korean and Spanish have no normalizer in this change and pass through. Supported languages also run the English adapter to retain cues in mixed text. Script detection cannot reliably distinguish Han-only Japanese from Chinese, or classify arbitrary Latin/mixed text. No language-detection dependency was added.

Counts below are row/document frequencies within each language, including duplicate descriptions. FP-only does not itself establish an activation cue; topic-only discriminators remain unnormalized. TP-only phrases are descriptive patterns/translation placeholders, not negative detector rules. Generic Chinese 使用/用于, Japanese 使用した/使用して, and Turkish için are insufficient alone. English cues immediately preceded by not/never and Chinese cues immediately preceded by 不 (including intervening whitespace) are left unchanged. Japanese negative usage endings and Turkish building clauses followed immediately by kullanma/kullanmayın/kullanmayınız are also left unchanged. These are local grammar guards, not a general semantic negation analysis.

## zh

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 当用户 | 7 | 0 | when user |
| 适用于 | 10 | 0 | use for |
| 时使用 | 10 | 0 | when using |
| 触发词： | 2 | 0 | trigger: |
| 触发条件： | 1 | 0 | trigger: |
| 触发时机： | 1 | 0 | trigger: |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| 专业知识 | FP only | 7 | Topic; unchanged |
| 年以上经验 | FP only | 5 | Topic; unchanged |
| 最佳实践 | TP only | 12 | No activation clause; unchanged |
| 测试模式 | TP only | 5 | No activation clause; unchanged |
| 测试策略 | TP only | 4 | No activation clause; unchanged |
| 应用程序 | TP only | 7 | No activation clause; unchanged |

## ja

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 場合にこのスキルを使用 | 1 | 0 | use this when |
| 場合に使用 | 20 | 0 | use when |
| ときに使用 | 2 | 0 | use when |
| 際に使用 | 1 | 0 | use when |
| 時に使用 | 1 | 0 | use when |
| ために使用 | 1 | 0 | used for |
| リクエストに使用 | 1 | 0 | use for requests |
| このスキルを使用してください | 1 | 0 | use this |
| トリガー:, トリガー： | 2 | 0 | trigger: |
| トリガーされます | 1 | 0 | triggered |
| ときにアクティベーション | 1 | 0 | trigger when |
| 開始時に | 1 | 0 | when starting |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| を構築します | FP only | 3 | Topic; unchanged |
| を生成します | FP only | 3 | Topic; unchanged |
| 日本語翻訳が必要です | TP only | 32 | No activation clause; unchanged |
| テスト戦略 | TP only | 4 | No activation clause; unchanged |
| セキュリティベストプラクティス | TP only | 1 | No activation clause; unchanged |

## tr

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| bu skill'i kullanın | 2 | 0 | use this |
| oluşturmak için | 3 | 0 | use for building |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| test kalıpları | FP only | 2 | Topic; unchanged |
| API tasarımı | FP only | 2 | Topic; unchanged |
| kapsamlı doğrulama sistemi | TP only | 1 | No activation clause; unchanged |
| evrensel kodlama standartları | TP only | 1 | No activation clause; unchanged |
| frontend geliştirme kalıpları | TP only | 1 | No activation clause; unchanged |

## en

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| for building | 5 | 0 | use for building |
| for interacting with and testing | 1 | 0 | use for interacting with and testing |
| for query optimization | 3 | 0 | use for query optimization |
| at logical intervals | 2 | 0 | when at logical intervals |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| best practices | FP only | 21 | Topic; unchanged |
| architecture patterns | FP only | 7 | Topic; unchanged |
| Windows native desktop apps | TP only | 1 | No activation clause; unchanged |
| development for Laravel | TP only | 1 | No activation clause; unchanged |
| terminal-style screen recording | TP only | 1 | No activation clause; unchanged |

## Reproduction and artifacts

```bash
PYTHONPATH=src python3 evals/gate_wiring/mine_h18_languages.py
```

Requires the existing private frozen corpus. Full tagged descriptions are saved separately in `.hermes/local/h18-language/fp.jsonl` and `tp.jsonl`. Source/finding provenance is retained. `lexical-phrases.json` contains every FP-only/TP-only 2–4 word gram and 3–20 character CJK gram from the requested four languages; `validation.jsonl` records before/after flags by finding identity. [Aggregate receipt](h18-language-results.json) pins inputs and output files by SHA-256.

The replay verifies every selected source against the manifest, every retained H1.8 identity, the unchanged English regex AST, and byte-identical other detector/gate/scanner files. H1's AST is unchanged after removing the new import and unwrapping the single H1.8 normalization call. Normalization is used only for the trigger check; source evidence, length thresholds, and other rules continue to use the original description.

No push or public release is part of this work.
