"""Turkish research adapter; delivered H1.8 skips Turkish descriptions."""

from pathlib import Path

import pytest

from lintlang.detectors.h1 import _SKILL_TRIGGER, _detect_skill_metadata
from lintlang.detectors.lang import detect, tr
from lintlang.models import AgentConfig, SkillMeta
from lintlang.scanner import scan_file


def h18(description: str):
    config = AgentConfig(kind="skill", skill=SkillMeta(
        name="turkish-skill", dir_name="turkish-skill", description=description,
        name_line=2, description_line=3,
    ))
    return [finding for finding in _detect_skill_metadata(config) if finding.code == "H1.8"]


@pytest.mark.parametrize("description", [
    # Each clause below is copied from the supplied Turkish FP descriptions.
    "Sorgu optimizasyonu, şema tasarımı, indeksleme ve güvenlik için PostgreSQL veritabanı kalıpları.",
    "web uygulamaları için üretim hazırlığı kontrol listeleri.",
    "üretim API'leri için hız sınırlama içerir.",
    "sıfır kesinti deployment'ları için veritabanı migration en iyi uygulamaları.",
    "multi-servis orkestrasyon için Docker ve Docker Compose kalıpları.",
    "Claude Code oturumlarından yeniden kullanılabilir kalıpları otomatik olarak çıkarın ve gelecekte kullanmak üzere öğrenilmiş skill'ler olarak kaydedin.",
])
def test_research_turkish_clauses_reach_canonical_regex(description):
    assert detect(description) == "tr"
    assert not _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(tr.normalize(description))
    assert not h18(description)


@pytest.mark.parametrize("description", [
    "Sorgu optimizasyonu için PostgreSQL rehberi.",
    "Yeni servislerin deployment'ları için migration rehberi.",
    "Dağıtık orkestrasyon için konteyner kontrol listesi.",
    "Uygulamanız için üretim hazırlığı kontrol listesi.",
    "Yeni API için hız sınırlama rehberi.",
    "Oturumdan yeniden kullanılabilir dersleri çıkarın.",
])
def test_mined_cues_generalize_beyond_the_source_description(description):
    assert _SKILL_TRIGGER.search(tr.normalize(description))
    assert not h18(description)


@pytest.mark.parametrize("description", [
    # Supplied Turkish TPs: generic için is not sufficient.
    "TypeScript, JavaScript, React ve Node.js geliştirme için evrensel kodlama standartları, en iyi uygulamalar ve kalıplar.",
    "React, Next.js, state yönetimi, performans optimizasyonu ve UI en iyi uygulamaları için frontend geliştirme kalıpları.",
    "Claude Code oturumları için kapsamlı doğrulama sistemi.",
    # Topic-only and method-only descriptions do not acquire a trigger.
    "Sorgu optimizasyonu, şema tasarımı ve indeksleme kalıpları.",
    "Üretim hazırlığı ve hız sınırlama en iyi uygulamaları.",
    "Deployment'ları ve orkestrasyon yöntemlerini açıklar.",
    "Hook'lar aracılığıyla oturumları gözlemleyen ve kontaminasyonu önlemek için instinct'ler ekleyen sistem.",
    "Claude Code oturumlarından kalıpları çıkarır ve kaydeder.",
    "pytest, TDD metodolojisi ve fixture'lar kullanarak Python test stratejileri.",
])
def test_research_turkish_topic_clauses_keep_text_and_integrated_rule_skips(description):
    assert tr.normalize(description) == description
    assert not _SKILL_TRIGGER.search(tr.normalize(description))
    assert not h18(description)


@pytest.mark.parametrize("description", [
    "Sorgu optimizasyonu, şema tasarımı ve indeksleme için kullanmayın.",
    "Web uygulamaları için üretim hazırlığı kontrol listesi değildir.",
    "Üretim API'leri için hız sınırlama içermez.",
    "Deployment'ları için kullanmayınız.",
    "Orkestrasyon için kullanma.",
    "Oturumdan kalıpları asla çıkarın.",
    "Oturumdan kalıpları çıkarmayın.",
])
def test_turkish_negative_clauses_do_not_become_activation(description):
    assert tr.normalize(description) == description
    assert not _SKILL_TRIGGER.search(tr.normalize(description))
    assert not h18(description)


def test_additional_turkish_fixture_has_no_structural_findings():
    path = Path(__file__).resolve().parents[1] / "samples/h18_languages/tr-additional-trigger/SKILL.md"
    result = scan_file(path, gate=False)
    assert not result.input_error
    assert result.inspected["skill_description"] == 1
    assert not result.structural_findings
