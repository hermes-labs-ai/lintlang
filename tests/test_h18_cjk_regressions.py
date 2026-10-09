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
])
def test_new_cues_exclude_negated_questions_and_method_clauses(description):
    assert normalize(description) == description
    result = _h18(description)
    assert len(result) == 1
    assert result[0].evidence == description[:120]


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


def test_additional_japanese_fixture_has_no_structural_findings():
    path = Path(__file__).resolve().parents[1] / "samples/h18_languages/ja-additional-trigger/SKILL.md"
    result = scan_file(path, gate=False)
    assert not result.input_error
    assert result.inspected["skill_description"] == 1
    assert not result.structural_findings
