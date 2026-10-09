"""H1.8 language routing, activation cues, and unchanged diagnostic boundaries."""

from pathlib import Path

import pytest

from lintlang.detectors.h1 import _SKILL_TRIGGER, _detect_skill_metadata
from lintlang.detectors.lang import detect, normalize
from lintlang.models import AgentConfig, Severity, SkillMeta
from lintlang.scanner import scan_file


def findings(description: str, name: str = "language-skill"):
    config = AgentConfig(kind="skill", skill=SkillMeta(
        name=name, dir_name="language-skill", description=description, name_line=2, description_line=3,
    ))
    return _detect_skill_metadata(config)


@pytest.mark.parametrize(("description", "language"), [
    ("當用戶準備報告", "zh"),
    ("使用情况", "zh"),
    ("𠀀", "zh"),
    ("漢字とひらがな", "ja"),
    ("カタカナと漢字", "ja"),
    ("ﾃｽﾄ", "ja"),
    ("한국어 漢字", "ko"),
    ("한", "ko"),
    ("Claude Code oturumları için kapsamlı doğrulama sistemi.", "tr"),
    ("pytest, TDD metodolojisi, fixture'lar, mocking, parametrizasyon ve coverage gereksinimleri kullanarak Python test stratejileri.", "tr"),
    ("BU SKILL'I KULLANIN.", "tr"),
    ("REST API design patterns including resource naming.", "en"),
    ("Build MCP servers with typed tools.", "en"),
    ("Schema design ・ query optimization", "en"),
    ("Patrones de diseño para aplicaciones.", "es"),
    ("", "en"),
])
def test_language_routing_uses_description_content(description, language):
    assert detect(description) == language


@pytest.mark.parametrize("description", [
    "当用户需要查询新的数据时使用。",
    "适用于处理新项目中的报告。",
    "触发词：报告审查。",
    "触发条件：提交新的项目。",
    "触发时机：收到部署计划。",
    "テストコードを追加する場合に使用します。",
    "新しいプロジェクトを作成するときに使用します。",
    "アイコンを追加する際に使用します。",
    "バグ修正、またはサービスのリファクタリング時に使用。",
    "ガイドを生成するために使用します。",
    "構造化リクエストに使用。",
    "セットアップする場合にこのスキルを使用する。",
    "次の場合は必ずこのスキルを使用してください: 環境を管理する場合。",
    "トリガー：新しいプロジェクト。",
    "トリガー: 新しいプロジェクト。",
    "プロジェクト作成についてトリガーされます。",
    "ユーザーがフレームワークに名前を付けるときにアクティベーション。",
    "セッション開始時にプロジェクトコンテキストを読み込みます。",
    "Yeni özellikler yazarken bu skill'i kullanın.",
    "BU SKILL'I KULLANIN.",
    "Sağlam uygulamaları oluşturmak için idiomatic Go kalıpları.",
    "Patterns for building a new application.",
    "Toolkit for interacting with and testing local web applications.",
    "Database patterns for query optimization.",
    "Compaction at logical intervals preserves the project context.",
])
def test_mined_activation_cues_reach_existing_english_gate(description):
    assert not _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(normalize(description))
    assert "H1.8" not in {finding.code for finding in findings(description)}


@pytest.mark.parametrize("description", [
    "Go测试模式包括表格驱动测试、子测试、基准测试、模糊测试和测试覆盖率。遵循TDD方法论，采用地道的Go实践。",
    "用于构建健壮、高效且可维护的Go应用程序的惯用Go模式、最佳实践和约定。",
    "pytest、TDD手法、フィクスチャ、モック、パラメータ化、カバレッジ要件を使用したPythonテスト戦略。",
    "並行レビューパスを使用して、スキルを分類します。",
    "日本語翻訳：このファイルは laravel-verification 用の日本語翻訳が必要です",
    "Claude Code oturumları için kapsamlı doğrulama sistemi.",
    "E2E testing for Windows native desktop apps using pywinauto.",
    "Test-driven development for Laravel with PHPUnit and Pest.",
    "Synthetic terminal-style screen recording guidance for Remotion TerminalScene.",
    "Browser and desktop automation discipline.",
    "项目配置的最佳实践、专业知识、模式、工具和示例。",
    "API implementation methods and best practices.",
    "Semantics for buildingblocks and databasequery optimization.",
])
def test_topic_and_method_descriptions_remain_flagged(description):
    result = [finding for finding in findings(description) if finding.code == "H1.8"]
    assert len(result) == 1
    assert result[0].evidence == description[:120]
    assert result[0].source_region.start_line == 3


@pytest.mark.parametrize("description", [
    "不触发词：调整现有项目中的简单配置和工具。",
    "不触发条件：在单个任务中处理现有项目数据。",
    "不触发时机：对现有项目执行简单的数据操作。",
    "トリガーしない場合：単一のタスクと既存のプロジェクト。",
    "This guide is not for query optimization.",
    "This guide is NOT   for query optimization.",
    "This guide is never for building applications.",
    "This guide is not for interacting with and testing local web applications.",
    "Compaction is not at logical intervals.",
    "此指南不适用于处理用户的项目配置和数据。",
    "此指南不  适用于处理用户的项目配置和数据。",
    "危険な既存プロジェクトの操作を追加する場合に使用しない。",
    "危険な既存プロジェクトの操作を追加する場合に使用しません。",
    "危険な既存プロジェクトの操作を追加するときに使用しない。",
    "危険な既存プロジェクトの操作を追加する際に使用しない。",
    "危険な既存プロジェクトの操作を追加時に使用しない。",
    "危険な既存プロジェクトの操作を追加するために使用しない。",
    "危険な既存プロジェクトの操作のリクエストに使用しない。",
    "危険な既存プロジェクトの操作を追加する場合にこのスキルを使用しない。",
    "Bu skill ile uygulamaları oluşturmak için kullanmayın.",
    "Bu skill ile uygulamaları oluşturmak için kullanmayınız.",
    "Bu skill ile uygulamaları oluşturmak için kullanma.",
])
def test_exclusion_heading_alone_does_not_become_positive_trigger(description):
    assert normalize(description) == description
    assert any(finding.code == "H1.8" for finding in findings(description))


@pytest.mark.parametrize("description", [
    "Use when the user asks for a report.",
    "Building a new tool with the user.",
    "About to cite a number whose source is a tracking doc.",
    "Before shipping the release.",
    "You need to write a report.",
    "Generate a diagram when 数据不足。",
])
def test_existing_english_triggers_are_preserved(description):
    assert _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not any(finding.code == "H1.8" for finding in findings(description))


@pytest.mark.parametrize("parenthetical", ["查询优化", "クエリ最適化", "veritabanı sorgusu"])
def test_supported_language_parenthetical_does_not_hide_mined_english_cue(parenthetical):
    description = f"Database patterns for query optimization ({parenthetical})."
    assert detect(description) != "en"
    assert _SKILL_TRIGGER.search(normalize(description))
    assert not any(finding.code == "H1.8" for finding in findings(description))


@pytest.mark.parametrize(("description", "language"), [
    ("훅을 통해 세션을 관찰하는 본능 기반 학습 시스템.", "ko"),
    ("Patrones para construir aplicaciones.", "es"),
    ("适用于数据管理。", "unknown"),
    ("當用戶需要檢查報告時使用。", "zh"),
])
def test_unsupported_language_or_unmined_spelling_passes_through(description, language):
    assert normalize(description, language) == description


@pytest.mark.parametrize(("length", "severity"), [(119, Severity.MEDIUM), (120, Severity.LOW)])
def test_h18_original_length_and_evidence_thresholds_are_preserved(length, severity):
    description = "測試模式" + "。" * (length - 4)
    result = [finding for finding in findings(description) if finding.code == "H1.8"]
    assert len(result) == 1
    assert result[0].severity is severity
    assert result[0].evidence == description[:120]


def test_normalization_does_not_change_other_skill_rules():
    description = "当用户需要新的报告时使用。" + "。" * 5000
    result = {finding.code: finding for finding in findings(description, name="WRONG_NAME")}
    assert set(result) == {"H1.7", "H1.9"}
    assert result["H1.7"].severity is Severity.HIGH
    assert f"{len(description)} characters" in result["H1.7"].description
    assert result["H1.7"].evidence == ""
    assert result["H1.9"].evidence == "WRONG_NAME"


@pytest.mark.parametrize("directory", ["zh-trigger", "ja-trigger", "tr-trigger", "en-trigger"])
def test_bundled_language_fixtures_have_no_h18_finding(directory):
    path = Path(__file__).resolve().parents[1] / "samples/h18_languages" / directory / "SKILL.md"
    result = scan_file(path, gate=False)
    assert not result.input_error
    assert result.inspected["skill_description"] == 1
    assert not result.structural_findings


def test_unmined_locale_folder_does_not_select_the_language(tmp_path):
    folder = tmp_path / "zh-CN" / "english-skill"
    folder.mkdir(parents=True)
    path = folder / "SKILL.md"
    path.write_text("---\nname: english-skill\ndescription: Database patterns for query optimization.\n---\n\nBody.\n")
    assert not scan_file(path, gate=False).structural_findings
