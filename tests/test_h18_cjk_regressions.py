"""Corpus-mined Japanese additions and conservative CJK residual behavior."""

from pathlib import Path

import pytest

from lintlang.detectors.h1 import _SKILL_TRIGGER, _detect_skill_metadata
from lintlang.detectors.lang import normalize
from lintlang.models import AgentConfig, SkillMeta
from lintlang.scanner import scan_file


def _h18(description: str):
    config = AgentConfig(kind="skill", skill=SkillMeta(
        name="cjk-regression", dir_name="cjk-regression", description=description,
        name_line=2, description_line=3,
    ))
    return [finding for finding in _detect_skill_metadata(config) if finding.code == "H1.8"]


@pytest.mark.parametrize("description", [
    # u-6e792b39af1e: social-graph-ranker, ja-JP.
    "XとLinkedInでのウォームイントロ発見、ブリッジスコアリング、ネットワークギャップ分析のための"
    "重み付きソーシャルグラフランキング。ユーザーがランキングエンジン自体を必要としている場合"
    "（より広いプロモーションやネットワーク維持ワークフローではなく）に使用する。",
    # u-87a3e9e53107: agent-architecture-audit, ja-JP.
    "エージェントおよび LLM アプリケーション向けのフルスタック診断。12 層のエージェントスタックに"
    "おけるラッパーリグレッション、メモリ汚染、ツール規律の失敗、隠れた修復ループ、レンダリング"
    "破損を監査します。重要度順の発見事項とコードファーストの修正を生成します。エージェント"
    "アプリケーション、自律ループ、または LLM を活用した機能を構築する開発者に必須です。",
    # u-b106d46f6c3b: database-migrations, ja-JP.
    "PostgreSQL、MySQL、一般的なORM（Prisma、Drizzle、Kysely、Django、TypeORM、golang-migrate）"
    "全体のスキーマ変更、データマイグレーション、ロールバック、ゼロダウンタイムデプロイメント"
    "のためのデータベースマイグレーションベストプラクティス。",
])
def test_additional_japanese_corpus_activation_cues(description):
    assert not _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not _h18(description)


@pytest.mark.parametrize("description", [
    "ユーザーがエンジン自体を必要としている場合（関連ワークフローではなく）に使用しない。",
    "ユーザーがエンジン自体を必要としている場合（関連ワークフローではなく）に使用しません。",
    "ユーザーがエンジン自体を必要としている場合（関連ワークフローではなく）に使用するな。",
    "ユーザーがエンジン自体を必要としている場合（関連ワークフローではなく）に使用する必要はありません。",
    "エージェントアプリケーションを構築する開発者に必須ではありません。",
    "エージェントアプリケーションを構築する開発者に必須ですか。",
    "ユーザーがエンジン自体を必要としている場合（関連ワークフローではなく）に使用した結果を表示します。",
    "構造化並行性を使用してアプリケーションを構築する開発者の作業を支援します。",
    "ユーザーがエンジン自体を必要としている場合（前の説明。別の文）に使用する。",
    "デプロイメントのためのベストプラクティスではない。",
    "デプロイメントのためのベストプラクティスではありません。",
    "デプロイメントのためのベストプラクティスではなく、設定値の一覧。",
    "デプロイメントのための作業は対象外です。",
    "デプロイメントのための手順を提供しません。",
    "デプロイメントのためのベストプラクティスですか。",
    "デプロイメントのためのテストデータを使用した検証方法。",
    "デプロイメントのためのテストデータを使用して結果を記録します。",
    "デプロイメントについてのベストプラクティスと設定の一覧。",
])
def test_new_cues_exclude_negated_questions_and_method_clauses(description):
    assert normalize(description) == description
    result = _h18(description)
    assert len(result) == 1
    assert result[0].evidence == description[:120]


def test_japanese_deployment_exclusion_stops_at_sentence_boundary():
    description = "デプロイメントのためのベストプラクティス。設定値を変更しません。"
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not _h18(description)


@pytest.mark.parametrize("description", [
    # Actual labeled TPs: don't turn generic purpose, method, or coverage into activation.
    "AI 支援開発のためのリグレッションテスト戦略。データベース依存なしのサンドボックスモード API テスト。",
    "pytest、TDD手法、フィクスチャ、モック、パラメータ化、カバレッジ要件を使用したPythonテスト戦略。",
    "库无关的Flutter/Dart代码审查清单，涵盖Widget最佳实践、状态管理模式和整洁架构。",
    "用于构建健壮、高效且可维护的Go应用程序的惯用Go模式、最佳实践和约定。",
    # Labeled FPs with no reliable activation clause: preserve rather than memorize topics.
    "生产就绪的 Dart 和 Flutter 模式，涵盖空安全、不可变状态、异步组合和整洁架构。",
    "视频与音频的查看、理解与行动。查看：从本地文件获取内容。理解：提取帧。行动：转码和标准化。",
    "本番環境対応のDartおよびFlutterパターンは、null安全性、不変状態、非同期構成をカバー。",
    "AgentShield を使用して、Claude Code の設定のセキュリティ脆弱性をスキャンします。",
])
def test_cjk_topic_and_method_only_descriptions_keep_h18(description):
    assert not _SKILL_TRIGGER.search(normalize(description))
    result = _h18(description)
    assert len(result) == 1
    assert result[0].evidence == description[:120]


@pytest.mark.parametrize("description", [
    # u-e90388e34391, data-scraper-agent.
    "适用于用户希望自动监控、收集或跟踪任何公共数据的场景。",
    # u-d7c5c0fc2b53, video-editing.
    "适用于用户想要编辑视频、剪辑素材、制作vlog或构建视频内容的情况。",
    # u-ddd648ea190c, production-scheduling.
    "适用于调度生产、解决瓶颈、优化换模、应对中断或平衡制造产线时。",
    # u-019875a222a0, quality-nonconformance.
    "适用于调查不合格、进行根本原因分析、管理纠正与预防措施、解释统计过程控制数据或处理供应商质量问题。",
    # u-ff75007087c4, customs-trade-compliance.
    "适用于处理海关清关、关税分类、贸易合规、进出口文件或关税优化时使用。",
])
def test_chinese_applicability_requires_mined_action_or_intent(description):
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not _h18(description)


@pytest.mark.parametrize("description", [
    "不适用于用户希望自动监控、收集或跟踪公共数据的场景。",
    "不  适用于用户想要编辑视频、剪辑素材或制作vlog的情况。",
    "不适用于调度生产、解决瓶颈或平衡制造产线。",
    "不适用于调查不合格、进行根本原因分析或管理纠正措施。",
    "不适用于处理海关清关、关税分类或贸易合规。",
    "不适用于处理海关清关、关税分类或贸易合规时使用。",
    "不触发条件：当用户想要处理已有项目中的数据时使用。",
    "不触发时机：当用户希望处理已有项目中的数据时使用。",
])
def test_chinese_mined_applicability_exclusions_remain_flagged(description):
    assert normalize(description) == description
    assert _h18(description)


def test_chinese_exclusion_scope_stops_at_sentence_boundary():
    description = "不适用于处理海关清关。适用于用户希望自动监控公共数据的场景。"
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not _h18(description)


@pytest.mark.parametrize("description", [
    # Broader labeled H1.8 TPs, including ESCALATE decisions. Do not convert
    # framework/team applicability or comparison topics into skill activation.
    # u-88ef53f26686, android-clean-architecture.
    "适用于Android和Kotlin多平台项目的Clean Architecture模式——模块结构、依赖规则、用例、仓库以及数据层模式。",
    # u-e342b70406d3, backend-patterns.
    "后端架构模式、API设计、数据库优化以及适用于Node.js、Express和Next.js API路由的服务器端最佳实践。",
    # u-7cfcdf0df67d, coding-standards.
    "适用于TypeScript、JavaScript、React和Node.js开发的通用编码标准、最佳实践和模式。",
    # u-a8100ac17eef, database-migrations.
    "数据库迁移最佳实践，涵盖模式变更、数据迁移、回滚以及零停机部署，适用于PostgreSQL、MySQL及常用ORM"
    "（Prisma、Drizzle、Django、TypeORM、golang-migrate）。",
    # u-2565c978e989, git-workflow.
    "Git工作流模式，包括分支策略、提交约定、合并与变基、冲突解决以及适用于各种规模团队的协作开发最佳实践。",
    # u-b155fb930274, liquid-glass-design.
    "iOS 26 液态玻璃设计系统 — 适用于 SwiftUI、UIKit 和 WidgetKit 的动态玻璃材质，具有模糊、反射和交互式变形效果。",
    # u-ae19340ee8cb, nextjs-turbopack.
    "Next.js 16+ 和 Turbopack — 增量打包、文件系统缓存、开发速度，以及何时使用 Turbopack 与 webpack。",
])
def test_broader_chinese_true_positives_keep_original_finding(description):
    assert normalize(description) == description
    result = _h18(description)
    assert len(result) == 1
    assert result[0].evidence == description[:120]
    assert result[0].source_region.start_line == 3


@pytest.mark.parametrize("language", ["ja", "zh"])
def test_additional_cjk_fixture_has_no_structural_findings(language):
    path = (Path(__file__).resolve().parents[1] / "samples/h18_languages"
            / f"{language}-additional-trigger/SKILL.md")
    result = scan_file(path, gate=False)
    assert not result.input_error
    assert result.inspected["skill_description"] == 1
    assert not result.structural_findings
