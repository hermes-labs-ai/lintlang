# H1.8 language trigger mining

Frozen 972-finding development corpus; the main replay uses the 172 FP / 126 TP KEEP cohort. Korean additionally uses the 15 labeled ko-KR H1.8 records in a separate supplemental replay. Historical/transferred and AI-review labels are preserved, not independently certified. Mining and evaluation use the same descriptions; this is a development replay, not held-out accuracy.

Actual scanner replay: FP **172 → 71** (101 removed, 58.72% reduction); TP **126 → 126** (100.00% retention).

| Description language | FP raw | FP before extension | FP after | TP before | TP after |
| --- | ---: | ---: | ---: | ---: | ---: |
| en | 54 | 43 | 43 | 3 | 3 |
| es | 37 | 37 | 10 | 0 | 0 |
| ja | 43 | 10 | 8 | 80 | 80 |
| ko | 1 | 1 | 1 | 7 | 7 |
| tr | 18 | 13 | 7 | 3 | 3 |
| zh | 19 | 2 | 2 | 33 | 33 |

The extension removes 35 additional FPs from commit `d980608`. 28 labeled non-English FPs remain flagged; the requested all-but-a-couple release criterion is not met. Some residual descriptions lack usage clauses, and similar translated descriptions have conflicting FP/TP labels. Suppressing topics merely because they occur only in the FP group would change H1.8 semantics.

A separate Korean replay includes all 15 labeled H1.8 records under `docs/ko-KR/skills/` in the same frozen corpus, including non-KEEP records. FP **3 → 1**; TP **12 → 12**. The two newly handled Korean FPs are `security-review` and `tdd-workflow`, both originally FP / ESCALATE. Their phrase was not present in the requested KEEP-only FP file. The original seven Korean TPs remain flagged. This supplemental result is not a 38-FP Korean replay.

Language tags come from content: kana → ja, Hangul → ko, Han → zh; Turkish spelling/ASCII cues handle Latin text. Spanish and Korean have mined normalizers. The supplied KEEP-only corpus contains one Korean FP and seven Korean TPs, rather than 38 Korean FPs. Its single FP describes a hook-based learning system without an activation clause and remains flagged. Korean's explicit use directive was mined separately from the additional labeled FP / ESCALATE descriptions. Supported languages also run the English adapter to retain cues in mixed text. Script detection cannot reliably distinguish Han-only Japanese from Chinese, or classify arbitrary Latin/mixed text. No language-detection dependency was added.

Counts below are row/document frequencies within each language, including duplicate descriptions. FP-only does not itself establish an activation cue; topic-only discriminators remain unnormalized. TP-only phrases are descriptive patterns/translation placeholders, not negative detector rules. Generic Chinese 使用/用于, Japanese 使用した/使用して, and Turkish için are insufficient alone. English cues immediately preceded by not/never and Chinese cues immediately preceded by 不 (including intervening whitespace) are left unchanged. Japanese negative usage endings and Turkish building clauses followed immediately by kullanma/kullanmayın/kullanmayınız are also left unchanged. These are local grammar guards, not a general semantic negation analysis.

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

## es

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| preparación para producción | 1 | 0 | use before production |
| Bucle de verificación para proyectos | 3 | 0 | use for project verification |
| antes del lanzamiento o PR | 2 | 0 | before release or PR |
| para construir aplicaciones | 4 | 0 | use for building applications |
| para optimización de consultas | 1 | 0 | use for query optimization |
| para cambios de esquema | 1 | 0 | use for schema changes |
| para diseño de entidades | 1 | 0 | use for entity design |
| para desarrollo local | 1 | 0 | use for local development |
| para APIs de producción | 1 | 0 | use for production APIs |
| para aplicaciones en producción | 1 | 0 | use for production applications |
| para autenticación/autorización | 2 | 0 | use for authentication/authorization |
| para autenticación | 3 | 0 | use for authentication |
| para pruebas inestables | 1 | 0 | use for flaky tests |
| para nomenclatura | 1 | 0 | use for naming |
| para mensajería | 1 | 0 | use for messaging |
| dirigir solicitudes de | 1 | 0 | route requests for |
| Usar este skill al | 2 | 0 | use this when |
| cuándo usar | 1 | 0 | when to use |
| Usar para | 1 | 0 | use for |
| Usar al | 2 | 0 | use when |

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| preparación para producción | u-4b6741626870 | affaan-m__ECC/docs/es/skills/deployment-patterns/SKILL.md |
| Bucle de verificación para proyectos | u-c94402990a58 | affaan-m__ECC/docs/es/skills/laravel-verification/SKILL.md |
| Bucle de verificación para proyectos | u-5795109d05ad | affaan-m__ECC/docs/es/skills/quarkus-verification/SKILL.md |
| Bucle de verificación para proyectos | u-ffbce8109b39 | affaan-m__ECC/docs/es/skills/springboot-verification/SKILL.md |
| antes del lanzamiento o PR | u-5795109d05ad | affaan-m__ECC/docs/es/skills/quarkus-verification/SKILL.md |
| antes del lanzamiento o PR | u-ffbce8109b39 | affaan-m__ECC/docs/es/skills/springboot-verification/SKILL.md |
| para construir aplicaciones | u-b67d581c06de | affaan-m__ECC/docs/es/skills/golang-patterns/SKILL.md |
| para construir aplicaciones | u-8eb2047d7e89 | affaan-m__ECC/docs/es/skills/kotlin-patterns/SKILL.md |
| para construir aplicaciones | u-bfed55328c0e | affaan-m__ECC/docs/es/skills/python-patterns/SKILL.md |
| para construir aplicaciones | u-9a849cd7fe0a | affaan-m__ECC/docs/es/skills/rust-patterns/SKILL.md |
| para optimización de consultas | u-841b28bb74f6 | affaan-m__ECC/docs/es/skills/postgres-patterns/SKILL.md |
| para cambios de esquema | u-801d10339c21 | affaan-m__ECC/docs/es/skills/database-migrations/SKILL.md |
| para diseño de entidades | u-b2070448f2ce | affaan-m__ECC/docs/es/skills/jpa-patterns/SKILL.md |
| para desarrollo local | u-83158259d3b8 | affaan-m__ECC/docs/es/skills/docker-patterns/SKILL.md |
| para APIs de producción | u-82eb68ee5ed4 | affaan-m__ECC/docs/es/skills/api-design/SKILL.md |
| para aplicaciones en producción | u-93db6bf71bad | affaan-m__ECC/docs/es/skills/laravel-patterns/SKILL.md |
| para autenticación/autorización | u-d5ecfaf88128 | affaan-m__ECC/docs/es/skills/laravel-security/SKILL.md |
| para autenticación/autorización | u-0d38fbc215d3 | affaan-m__ECC/docs/es/skills/springboot-security/SKILL.md |
| para autenticación | u-d5ecfaf88128 | affaan-m__ECC/docs/es/skills/laravel-security/SKILL.md |
| para autenticación | u-cbf02ccc5535 | affaan-m__ECC/docs/es/skills/quarkus-security/SKILL.md |
| para autenticación | u-0d38fbc215d3 | affaan-m__ECC/docs/es/skills/springboot-security/SKILL.md |
| para pruebas inestables | u-8054ae437e70 | affaan-m__ECC/docs/es/skills/e2e-testing/SKILL.md |
| para nomenclatura | u-1e3d0a84a6ff | affaan-m__ECC/docs/es/skills/coding-standards/SKILL.md |
| para mensajería | u-7e853c3225d1 | affaan-m__ECC/docs/es/skills/quarkus-patterns/SKILL.md |
| dirigir solicitudes de | u-a344104da112 | affaan-m__ECC/docs/es/skills/continuous-learning/SKILL.md |
| Usar este skill al | u-90c3df5f61fc | affaan-m__ECC/docs/es/skills/security-review/SKILL.md |
| Usar este skill al | u-1afd40108b17 | affaan-m__ECC/docs/es/skills/tdd-workflow/SKILL.md |
| cuándo usar | u-e838da51166e | affaan-m__ECC/docs/es/skills/nextjs-turbopack/SKILL.md |
| Usar para | u-1541de2ea2aa | affaan-m__ECC/docs/es/skills/springboot-patterns/SKILL.md |
| Usar al | u-71b8b4d84278 | affaan-m__ECC/docs/es/skills/quarkus-tdd/SKILL.md |
| Usar al | u-34a61c69e625 | affaan-m__ECC/docs/es/skills/springboot-tdd/SKILL.md |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| patrones | FP only | 22 | Topic; unchanged |

## ja

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 場合（より広いプロモーションやネットワーク維持ワークフローではなく）に使用する | 1 | 0 | use when |
| 構築する開発者に必須です | 1 | 0 | use for developers building |
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

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| 場合（より広いプロモーションやネットワーク維持ワークフローではなく）に使用する | u-6e792b39af1e | affaan-m__ECC/docs/ja-JP/skills/social-graph-ranker/SKILL.md |
| 構築する開発者に必須です | u-87a3e9e53107 | affaan-m__ECC/docs/ja-JP/skills/agent-architecture-audit/SKILL.md |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| を構築します | FP only | 3 | Topic; unchanged |
| を生成します | FP only | 3 | Topic; unchanged |
| 日本語翻訳が必要です | TP only | 32 | No activation clause; unchanged |
| テスト戦略 | TP only | 4 | No activation clause; unchanged |
| セキュリティベストプラクティス | TP only | 1 | No activation clause; unchanged |

## ko

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 시 이 스킬을 사용하세요 | 2 | 0 | use this when |

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| 시 이 스킬을 사용하세요 | u-4523f71beaef | affaan-m__ECC/docs/ko-KR/skills/security-review/SKILL.md |
| 시 이 스킬을 사용하세요 | u-eed217343bb1 | affaan-m__ECC/docs/ko-KR/skills/tdd-workflow/SKILL.md |

This phrase table uses the separate 3-FP / 12-TP Korean cohort described above. The single KEEP-only FP, `u-34b071729eea` (`docs/ko-KR/skills/continuous-learning-v2/SKILL.md`), describes internal observation/learning and a feature announcement. The generic `위한` purpose marker also occurs in six of the original seven Korean TPs and is deliberately left unchanged.

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| 본능 기반 학습 시스템 | FP only | 1 | Topic; unchanged |
| 범용 코딩 표준 | TP only | 1 | No activation clause; unchanged |

## tr

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| Sorgu optimizasyonu, şema tasarımı, indeksleme ve güvenlik için | 1 | 0 | use for query optimization |
| için üretim hazırlığı | 1 | 0 | use for production readiness |
| için hız sınırlama | 1 | 0 | use for rate limiting |
| deployment'ları için | 1 | 0 | use for deployments |
| orkestrasyon için | 1 | 0 | use for orchestration |
| çıkarın | 1 | 0 | use to extract |
| bu skill'i kullanın | 2 | 0 | use this |
| oluşturmak için | 3 | 0 | use for building |

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| Sorgu optimizasyonu, şema tasarımı, indeksleme ve güvenlik için | u-565265c5f7ec | affaan-m__ECC/docs/tr/skills/postgres-patterns/SKILL.md |
| için üretim hazırlığı | u-cb937cb9f59f | affaan-m__ECC/docs/tr/skills/deployment-patterns/SKILL.md |
| için hız sınırlama | u-390e93ea4d84 | affaan-m__ECC/docs/tr/skills/api-design/SKILL.md |
| deployment'ları için | u-88ae4028433e | affaan-m__ECC/docs/tr/skills/database-migrations/SKILL.md |
| orkestrasyon için | u-a732d5b69c22 | affaan-m__ECC/docs/tr/skills/docker-patterns/SKILL.md |
| çıkarın | u-2eb887f210fd | affaan-m__ECC/docs/tr/skills/continuous-learning/SKILL.md |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| test kalıpları | FP only | 2 | Topic; unchanged |
| API tasarımı | FP only | 2 | Topic; unchanged |
| kapsamlı doğrulama sistemi | TP only | 1 | No activation clause; unchanged |
| evrensel kodlama standartları | TP only | 1 | No activation clause; unchanged |
| frontend geliştirme kalıpları | TP only | 1 | No activation clause; unchanged |

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

## Remaining non-English FP descriptions

These are the frozen labels, not an assertion that every description contains an activation clause.

| Language | Finding | Skill description |
| --- | --- | --- |
| es | u-e4e279b1621e | affaan-m__ECC/docs/es/skills/backend-patterns/SKILL.md |
| es | u-ce76f0897b5c | affaan-m__ECC/docs/es/skills/continuous-learning-v2/SKILL.md |
| es | u-da1b9c7895f3 | affaan-m__ECC/docs/es/skills/django-patterns/SKILL.md |
| es | u-248bf0b8024a | affaan-m__ECC/docs/es/skills/eval-harness/SKILL.md |
| es | u-59c7725f84c3 | affaan-m__ECC/docs/es/skills/frontend-patterns/SKILL.md |
| es | u-b634ce5a316d | affaan-m__ECC/docs/es/skills/golang-testing/SKILL.md |
| es | u-da1fcbf7ebf1 | affaan-m__ECC/docs/es/skills/kotlin-testing/SKILL.md |
| es | u-ef674f09959c | affaan-m__ECC/docs/es/skills/laravel-tdd/SKILL.md |
| es | u-a68aa3c1ea95 | affaan-m__ECC/docs/es/skills/python-testing/SKILL.md |
| es | u-87e8c5ae6340 | affaan-m__ECC/docs/es/skills/rust-testing/SKILL.md |
| ja | u-5250c8076350 | affaan-m__ECC/docs/ja-JP/skills/agent-payment-x402/SKILL.md |
| ja | u-62ce1b261953 | affaan-m__ECC/docs/ja-JP/skills/agentic-os/SKILL.md |
| ja | u-529136c0f3ef | affaan-m__ECC/docs/ja-JP/skills/dart-flutter-patterns/SKILL.md |
| ja | u-b106d46f6c3b | affaan-m__ECC/docs/ja-JP/skills/database-migrations/SKILL.md |
| ja | u-4de9fada3dec | affaan-m__ECC/docs/ja-JP/skills/flutter-dart-code-review/SKILL.md |
| ja | u-098a09d39d72 | affaan-m__ECC/docs/ja-JP/skills/nodejs-keccak256/SKILL.md |
| ja | u-4dccce85e5d4 | affaan-m__ECC/docs/ja-JP/skills/security-scan/SKILL.md |
| ja | u-a7ceb2918330 | affaan-m__ECC/docs/ja-JP/skills/videodb/SKILL.md |
| ko | u-34b071729eea | affaan-m__ECC/docs/ko-KR/skills/continuous-learning-v2/SKILL.md |
| tr | u-86bf327de7e0 | affaan-m__ECC/docs/tr/skills/backend-patterns/SKILL.md |
| tr | u-4fb2ccf455dd | affaan-m__ECC/docs/tr/skills/continuous-learning-v2/SKILL.md |
| tr | u-0b67ec93274e | affaan-m__ECC/docs/tr/skills/django-patterns/SKILL.md |
| tr | u-fea731695a09 | affaan-m__ECC/docs/tr/skills/e2e-testing/SKILL.md |
| tr | u-18dbd8f40ce7 | affaan-m__ECC/docs/tr/skills/golang-testing/SKILL.md |
| tr | u-4eb0a6a1aa61 | affaan-m__ECC/docs/tr/skills/kotlin-testing/SKILL.md |
| tr | u-fbee1f8a3df9 | affaan-m__ECC/docs/tr/skills/python-testing/SKILL.md |
| zh | u-90b88dd7c15e | affaan-m__ECC/docs/zh-CN/skills/dart-flutter-patterns/SKILL.md |
| zh | u-d9c98f0d3894 | affaan-m__ECC/docs/zh-CN/skills/videodb/SKILL.md |

## Reproduction and artifacts

```bash
PYTHONPATH=src python3 evals/gate_wiring/mine_h18_languages.py
```

Requires the existing private frozen corpus. Full tagged descriptions are saved separately in `.hermes/local/h18-language/fp.jsonl` and `tp.jsonl`. Source/finding provenance is retained. `lexical-phrases.json` contains every FP-only/TP-only 2–4 word gram (including Korean eojeol) and 3–20 character Chinese/Japanese gram from the six tagged languages; `validation.jsonl` records before/after flags by finding identity. The Korean supplemental descriptions and replay live in `korean-all-labeled.jsonl` and `korean-validation.jsonl`; the original KEEP-only files are preserved. [Aggregate receipt](h18-language-results.json) pins inputs and output files by SHA-256.

The replay verifies every selected source against the manifest, every retained H1.8 identity, the unchanged English regex AST, and byte-identical other detector/gate/scanner files. H1's AST is unchanged after removing the new import and unwrapping the single H1.8 normalization call. Normalization is used only for the trigger check; source evidence, length thresholds, and other rules continue to use the original description.

No push or public release is part of this work.
