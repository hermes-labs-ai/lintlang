"""Research-only Spanish clauses, semantic exclusions, and H1.8 scope."""

from pathlib import Path

import pytest

from lintlang.detectors.h1 import _SKILL_TRIGGER
from lintlang.detectors.lang import es
from lintlang.scanner import scan_file

# One frozen source clause for every map entry, not invented dictionary phrases.
_MINED = (
    ("u-4b6741626870", "listas de verificación de preparación para producción de aplicaciones web."),
    ("u-c94402990a58", "Bucle de verificación para proyectos Laravel: verificaciones de entorno."),
    ("u-5795109d05ad", "revisión de diff antes del lanzamiento o PR."),
    ("u-b67d581c06de", "convenciones para construir aplicaciones Go robustas, eficientes y mantenibles."),
    ("u-841b28bb74f6", "Patrones de base de datos PostgreSQL para optimización de consultas."),
    ("u-801d10339c21", "Buenas prácticas de migración de base de datos para cambios de esquema."),
    ("u-b2070448f2ce", "Patrones JPA/Hibernate para diseño de entidades, relaciones."),
    ("u-83158259d3b8", "Patrones de Docker y Docker Compose para desarrollo local."),
    ("u-82eb68ee5ed4", "rate limiting para APIs de producción."),
    ("u-93db6bf71bad", "API resources para aplicaciones en producción."),
    ("u-d5ecfaf88128", "Buenas prácticas de seguridad en Laravel para autenticación/autorización, validación."),
    ("u-cbf02ccc5535", "Buenas prácticas de seguridad en Quarkus para autenticación, autorización, JWT/OIDC."),
    ("u-8054ae437e70", "gestión de artefactos y estrategias para pruebas inestables."),
    ("u-1e3d0a84a6ff", "Convenciones de codificación base entre proyectos para nomenclatura, legibilidad."),
    ("u-7e853c3225d1", "Patrones de arquitectura Quarkus 3.x LTS con Camel para mensajería."),
    ("u-a344104da112", "dirigir solicitudes de aprendizaje continuo, aprendizaje de sesión."),
    ("u-90c3df5f61fc", "Usar este skill al agregar autenticación, manejar entradas de usuario."),
    ("u-e838da51166e", "Next.js 16+ y Turbopack — cuándo usar Turbopack frente a webpack."),
    ("u-1541de2ea2aa", "Usar para trabajo de backend en Java con Spring Boot."),
    ("u-71b8b4d84278", "Usar al agregar funcionalidades, corregir bugs o refactorizar servicios orientados a eventos."),
)


@pytest.mark.parametrize(("finding_id", "description"), _MINED, ids=[row[0] for row in _MINED])
def test_each_mined_spanish_clause_reaches_research_english_gate(finding_id, description):
    assert not _SKILL_TRIGGER.search(description)
    assert _SKILL_TRIGGER.search(es.normalize(description)), finding_id


def test_every_map_entry_has_a_distinct_source_clause():
    assert len(es._MAP) == len(_MINED)
    for (pattern, _), (_, description) in zip(es._COMPILED, _MINED, strict=True):
        assert pattern.search(description)


@pytest.mark.parametrize(("finding_id", "description"), _MINED, ids=[row[0] for row in _MINED])
@pytest.mark.parametrize("prefix", ["No ", "NUNCA ", "No es ", "Jamás se debe "])
def test_negated_spanish_cues_do_not_become_triggers(finding_id, description, prefix):
    text = prefix + description
    assert es.normalize(text) == text, finding_id
    assert not _SKILL_TRIGGER.search(text)


@pytest.mark.parametrize("description", [
    # Corpus residuals: topic/method lists and feature behavior are not selectors.
    "Patrones de arquitectura Django, diseño de API REST con DRF, buenas prácticas de ORM.",
    "Patrones de pruebas Go incluyendo pruebas basadas en tablas, subpruebas y cobertura de código.",
    "Patrones de pruebas Kotlin con Kotest, MockK. Sigue la metodología TDD.",
    "Estrategias de pruebas Python usando pytest, metodología TDD, fixtures y mocking.",
    "Patrones de pruebas en Rust incluyendo pruebas unitarias. Sigue la metodología TDD.",
    "Sistema de aprendizaje basado en instintos que observa sesiones mediante hooks.",
    "v2.1 agrega instintos con alcance de proyecto para prevenir contaminación entre proyectos.",
    "Patrones de arquitectura backend para Node.js, Express y rutas API de Next.js.",
    "Patrones de desarrollo frontend para React, Next.js, gestión de estado y buenas prácticas de UI.",
    "Framework formal de evaluación para sesiones de Claude Code.",
    # Spanish versions of known true-positive task/topic descriptions.
    "Desarrollo guiado por pruebas para Laravel con PHPUnit y Pest, factories y objetivos de cobertura.",
    "Pruebas E2E para aplicaciones de escritorio nativas de Windows usando pywinauto.",
    "Sistema integral de verificación para sesiones de Claude Code.",
    "Guía de grabación de pantalla de estilo terminal sintético para Remotion TerminalScene.",
    # Bare prepositions and topics must not be translated into selection cues.
    "Guía para aplicaciones y prácticas de desarrollo.",
    "Resumen sobre autenticación, diseño de entidades, cambios de esquema y nomenclatura.",
])
def test_spanish_topics_methods_and_feature_purposes_remain_flaggable(description):
    assert es.normalize(description) == description
    assert not _SKILL_TRIGGER.search(es.normalize(description))


def test_spanish_positive_clause_after_negated_sentence_still_works():
    description = "No es una guía de temas. Usar este skill al agregar autenticación."
    assert _SKILL_TRIGGER.search(es.normalize(description))


def test_spanish_sample_is_outside_h18_scope(monkeypatch):
    def forbidden(_text):
        raise AssertionError("H1.8 invoked the research-only Spanish normalizer")

    monkeypatch.setattr(es, "normalize", forbidden)
    path = Path(__file__).resolve().parents[1] / "samples/h18_languages/es-trigger/SKILL.md"
    result = scan_file(path, gate=False)
    assert not result.input_error
    assert result.inspected["skill_description"] == 1
    assert not result.structural_findings
