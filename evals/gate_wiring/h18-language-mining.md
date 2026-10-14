# H1.8 language scope and trigger replay

H1.8 runs only for descriptions routed by content to Chinese, Japanese, or Korean. Other languages produce no H1.8 finding and are excluded from FP/TP counts. English, Spanish, and Turkish modules remain available for research and are not invoked by H1.8, including as a fallback for CJK text. Other detector rules and the English trigger regex are unchanged.

The frozen 972-finding corpus uses historical/transferred and AI-review labels, not independently certified labels. Mining and evaluation use the same descriptions; these are development replays, not held-out accuracy or production precision estimates.

Before language scoping, the repaired adapters retained **272/272** labeled H1.8 TPs. The repair restored seven Chinese TP findings outside the KEEP cohort. The CJK mapping digests were frozen after this validation and verified unchanged during scoping.

After scoping, all **272** TP inputs are accounted for: **249 retained CJK TPs** and **23 excluded non-CJK records**. Retention among eligible TPs is **249/249**. Excluded records are not counted as false negatives.

| Language | TP input | Eligible | Retained | Excluded |
| --- | ---: | ---: | ---: | ---: |
| en | 18 | 0 | 0 | 18 |
| es | 1 | 0 | 0 | 1 |
| ja | 141 | 141 | 141 | 0 |
| ko | 12 | 12 | 12 | 0 |
| tr | 4 | 0 | 0 | 4 |
| zh | 96 | 96 | 96 | 0 |

## FP replay

The supplied KEEP-only FP/TP files remain unchanged. Their original inputs include one Korean FP and seven Korean TPs. Counts below exclude languages outside the new scope.

| Language | KEEP FP input | Remaining FP | Excluded FP | KEEP TP retained |
| --- | ---: | ---: | ---: | ---: |
| en | 54 | 0 | 54 | 0 |
| es | 37 | 0 | 37 | 0 |
| ja | 43 | 7 | 0 | 80 |
| ko | 1 | 1 | 0 | 7 |
| tr | 18 | 0 | 18 | 0 |
| zh | 19 | 2 | 0 | 33 |

KEEP-only inputs: 172 FPs, of which 109 are excluded; eligible FP findings **63 → 10**. Eligible KEEP TPs **120/120** retained.

The broader FP replay also covers every labeled H1.8 FP in the frozen corpus, across gate decisions.

| Language | All FP input | Remaining FP | Excluded FP |
| --- | ---: | ---: | ---: |
| en | 59 | 0 | 59 |
| es | 37 | 0 | 37 |
| ja | 67 | 14 | 0 |
| ko | 3 | 1 | 0 |
| tr | 18 | 0 | 18 |
| zh | 82 | 19 | 0 |

The Korean supplemental cohort contains all 15 labeled H1.8 records under `docs/ko-KR/skills/`, including non-KEEP records. FP **3 → 1**; TP **12/12**. The two explicit usage clauses came from `security-review` and `tdd-workflow` (FP / ESCALATE). This result is separate from the original KEEP-only Korean 1-FP / 7-TP cohort; counts overlap.

## Routing and boundaries

Content-based routing checks kana, Hangul, then Han. Turkish/Spanish spelling cues classify Latin text for reporting; other Latin text routes to English and is outside H1.8 scope. Folder locales do not select the language. Han-only Japanese and arbitrary mixed text cannot be classified reliably.

The Chinese adapter requires mined task/intent clauses after `适用于`, and leaves the comparison-topic phrase `何时使用` unchanged. Generic Chinese 使用/用于/适用于, Japanese 使用した/使用して, and Korean 위한 are insufficient alone. Negation guards are local grammar checks, not general semantic analysis. Original evidence, length thresholds, severity, and other rules continue to use unmodified descriptions.

## en: research only; not invoked by H1.8

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

## es: research only; not invoked by H1.8

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

## ja: active H1.8 mapping

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 場合（より広いプロモーションやネットワーク維持ワークフローではなく）に使用する | 1 | 0 | use when |
| 構築する開発者に必須です | 1 | 0 | use for developers building |
| デプロイメントのための | 1 | 0 | use for deployments |
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
| デプロイメントのための | u-b106d46f6c3b | affaan-m__ECC/docs/ja-JP/skills/database-migrations/SKILL.md |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| を構築します | FP only | 3 | Topic; unchanged |
| を生成します | FP only | 3 | Topic; unchanged |
| 日本語翻訳が必要です | TP only | 32 | No activation clause; unchanged |
| テスト戦略 | TP only | 4 | No activation clause; unchanged |
| セキュリティベストプラクティス | TP only | 1 | No activation clause; unchanged |

## ko: active H1.8 mapping

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 시 이 스킬을 사용하세요 | 2 | 0 | use this when |

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| 시 이 스킬을 사용하세요 | u-4523f71beaef | affaan-m__ECC/docs/ko-KR/skills/security-review/SKILL.md |
| 시 이 스킬을 사용하세요 | u-eed217343bb1 | affaan-m__ECC/docs/ko-KR/skills/tdd-workflow/SKILL.md |

Korean mining uses the separately scoped 3-FP / 12-TP supplemental cohort. The KEEP-only FP `continuous-learning-v2` describes internal behavior and remains flagged.

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| 본능 기반 학습 시스템 | FP only | 1 | Topic; unchanged |
| 범용 코딩 표준 | TP only | 1 | No activation clause; unchanged |

## tr: research only; not invoked by H1.8

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

## zh: active H1.8 mapping

| Mined FP-only cue | FP rows | TP rows | Canonical English |
| --- | ---: | ---: | --- |
| 适用于用户希望 | 1 | 0 | use when user wants |
| 适用于用户想要 | 1 | 0 | use when user wants |
| 适用于调度 | 1 | 0 | use for scheduling |
| 适用于调查 | 1 | 0 | use for investigating |
| 适用于处理 | 2 | 0 | use for handling |
| 当用户 | 7 | 0 | when user |
| 时使用 | 10 | 0 | when using |
| 触发词： | 2 | 0 | trigger: |
| 触发条件： | 1 | 0 | trigger: |
| 触发时机： | 1 | 0 | trigger: |

| New cue source | Finding | FP skill description |
| --- | --- | --- |
| 适用于用户希望 | u-e90388e34391 | affaan-m__ECC/docs/zh-CN/skills/data-scraper-agent/SKILL.md |
| 适用于用户想要 | u-d7c5c0fc2b53 | affaan-m__ECC/docs/zh-CN/skills/video-editing/SKILL.md |
| 适用于调度 | u-ddd648ea190c | affaan-m__ECC/docs/zh-CN/skills/production-scheduling/SKILL.md |
| 适用于调查 | u-019875a222a0 | affaan-m__ECC/docs/zh-CN/skills/quality-nonconformance/SKILL.md |
| 适用于处理 | u-ff75007087c4 | affaan-m__ECC/docs/zh-CN/skills/customs-trade-compliance/SKILL.md |
| 适用于处理 | u-e32a829e3ed8 | affaan-m__ECC/docs/zh-CN/skills/returns-reverse-logistics/SKILL.md |
| 时使用 | u-720946518d0b | affaan-m__ECC/docs/ja-JP/skills/openclaw-persona-forge/SKILL.md |
| 时使用 | u-7b47703a52d6 | affaan-m__ECC/docs/zh-CN/skills/autonomous-agent-harness/SKILL.md |
| 时使用 | u-472b9bfaf5c3 | affaan-m__ECC/docs/zh-CN/skills/carrier-relationship-management/SKILL.md |
| 时使用 | u-ff75007087c4 | affaan-m__ECC/docs/zh-CN/skills/customs-trade-compliance/SKILL.md |
| 时使用 | u-ed60e7f1204d | affaan-m__ECC/docs/zh-CN/skills/energy-procurement/SKILL.md |
| 时使用 | u-1960a9694699 | affaan-m__ECC/docs/zh-CN/skills/fal-ai-media/SKILL.md |
| 时使用 | u-b57922c7e46a | affaan-m__ECC/docs/zh-CN/skills/github-ops/SKILL.md |
| 时使用 | u-ceb3857e91f9 | affaan-m__ECC/docs/zh-CN/skills/inventory-demand-planning/SKILL.md |
| 时使用 | u-fd7f9ba7d456 | affaan-m__ECC/docs/zh-CN/skills/lead-intelligence/SKILL.md |
| 时使用 | u-e32a829e3ed8 | affaan-m__ECC/docs/zh-CN/skills/returns-reverse-logistics/SKILL.md |

| Other distinguishing phrase | Group | Rows | Handling |
| --- | --- | ---: | --- |
| 专业知识 | FP only | 7 | Topic; unchanged |
| 年以上经验 | FP only | 5 | Topic; unchanged |
| 最佳实践 | TP only | 12 | No activation clause; unchanged |
| 测试模式 | TP only | 5 | No activation clause; unchanged |
| 测试策略 | TP only | 4 | No activation clause; unchanged |
| 应用程序 | TP only | 7 | No activation clause; unchanged |

## Remaining KEEP-only CJK FP descriptions

| Language | Finding | Skill description |
| --- | --- | --- |
| ja | u-5250c8076350 | affaan-m__ECC/docs/ja-JP/skills/agent-payment-x402/SKILL.md |
| ja | u-62ce1b261953 | affaan-m__ECC/docs/ja-JP/skills/agentic-os/SKILL.md |
| ja | u-529136c0f3ef | affaan-m__ECC/docs/ja-JP/skills/dart-flutter-patterns/SKILL.md |
| ja | u-4de9fada3dec | affaan-m__ECC/docs/ja-JP/skills/flutter-dart-code-review/SKILL.md |
| ja | u-098a09d39d72 | affaan-m__ECC/docs/ja-JP/skills/nodejs-keccak256/SKILL.md |
| ja | u-4dccce85e5d4 | affaan-m__ECC/docs/ja-JP/skills/security-scan/SKILL.md |
| ja | u-a7ceb2918330 | affaan-m__ECC/docs/ja-JP/skills/videodb/SKILL.md |
| ko | u-34b071729eea | affaan-m__ECC/docs/ko-KR/skills/continuous-learning-v2/SKILL.md |
| zh | u-90b88dd7c15e | affaan-m__ECC/docs/zh-CN/skills/dart-flutter-patterns/SKILL.md |
| zh | u-d9c98f0d3894 | affaan-m__ECC/docs/zh-CN/skills/videodb/SKILL.md |

## Reproduction and artifacts

```bash
PYTHONPATH=src python3 evals/gate_wiring/mine_h18_languages.py
```

Requires the existing private frozen corpus. Full descriptions and finding-level outcomes remain in `.hermes/local/h18-language/`: `fp.jsonl`, `tp.jsonl`, `validation.jsonl`, `korean-all-labeled.jsonl`, `korean-validation.jsonl`, `all-h18-tp.jsonl`, `all-h18-tp-validation.jsonl`, `all-h18-fp.jsonl`, and `all-h18-fp-validation.jsonl`. Input and output digests are pinned in the [aggregate receipt](h18-language-results.json).

The replay verifies every source against the frozen manifest and every retained finding identity. It also verifies the English trigger regex AST, byte-identical unrelated detector/gate/scanner files, and H1 AST equality after unwrapping only the H1.8 language guard and normalization call. The pre-scope TP receipt and CJK mapping digests are retained in the aggregate receipt.

No push or public release is part of this work.
