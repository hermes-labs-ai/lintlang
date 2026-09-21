"""Compatibility checks for the split models and H1 modules."""

from dataclasses import fields

import lintlang.detectors.h1 as h1
import lintlang.models as models
import lintlang.patterns as patterns


def test_model_reexports_are_identical() -> None:
    for name in (
        "AgentConfig",
        "Finding",
        "Severity",
        "SkillMeta",
        "SourceRegion",
        "ToolDef",
        "is_localization_reference",
    ):
        assert getattr(patterns, name) is getattr(models, name)


def test_current_model_fields_are_preserved() -> None:
    expected = {
        "SourceRegion": ("start_line", "end_line"),
        "Finding": (
            "pattern_id",
            "pattern_name",
            "severity",
            "location",
            "description",
            "suggestion",
            "evidence",
            "sub_id",
            "source_region",
            "offset",
        ),
        "SkillMeta": (
            "name",
            "description",
            "has_name",
            "has_description",
            "name_line",
            "description_line",
            "dir_name",
        ),
        "AgentConfig": (
            "tools",
            "system_prompt",
            "messages",
            "schemas",
            "constraints",
            "raw",
            "source_file",
            "source_region",
            "kind",
            "unclaimed",
            "uninspected_text",
            "dropped",
            "not_agent_content",
            "prompt_paths",
            "skill",
            "prompt_line_offset",
        ),
        "ToolDef": ("name", "description", "parameters", "path", "group", "owner", "has_schema"),
    }

    for name, field_names in expected.items():
        assert tuple(field.name for field in fields(getattr(models, name))) == field_names


def test_h1_reexports_are_identical() -> None:
    names = (
        "VAGUE_WORDS",
        "_ALIAS_NOTICE",
        "_CAMEL_BOUNDARY",
        "_GENERIC_CANONICALS",
        "_IDENTIFIER_SHAPED",
        "_LOW_INFORMATION",
        "_MIN_ANALYSABLE_TERMS",
        "_NON_DISCRIMINATING",
        "_SKILL_DESCRIPTION_LIMIT",
        "_SKILL_NAME",
        "_SKILL_NAME_LIMIT",
        "_SKILL_TRIGGER",
        "_STOPWORDS",
        "_SUFFIXES",
        "_SYNONYM_CLASS",
        "_SYNONYM_GROUPS",
        "_canonical",
        "_cross_references",
        "_declared_alias",
        "_detect_skill_metadata",
        "_differentia",
        "_distinct_input_shapes",
        "_domination_is_meaningful",
        "_is_analysable",
        "_leading_verb",
        "_meaning_terms",
        "_split_identifiers",
        "_stem_candidates",
        "_word_overlap",
        "detect_h1",
    )

    for name in names:
        assert getattr(patterns, name) is getattr(h1, name)


def test_registry_keeps_h1_identity_and_order() -> None:
    assert tuple(patterns.PATTERNS) == ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
    assert patterns.PATTERNS["H1"]["detect"] is h1.detect_h1
