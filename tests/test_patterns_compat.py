"""Compatibility proof for the patterns.py -> models.py/detectors.h1 split.

These tests exist to prove the refactor is behavior-preserving at the import
boundary: every name that used to live in `lintlang.patterns` must still be
importable from there, and the shared model classes must be the *same
objects* (not equal copies) whichever module they are imported from, so that
`isinstance` checks anywhere in the codebase keep working.
"""

import lintlang.detectors.h1 as h1
import lintlang.models as models
import lintlang.patterns as patterns


class TestPublicSurfaceStillImportable:
    def test_shared_models_importable_from_patterns(self):
        from lintlang.patterns import (  # noqa: F401
            AgentConfig,
            Finding,
            Severity,
            SourceRegion,
            ToolDef,
        )

    def test_h1_detector_and_helpers_importable_from_patterns(self):
        from lintlang.patterns import (  # noqa: F401
            VAGUE_WORDS,
            _differentia,
            _meaning_terms,
            _word_overlap,
            detect_h1,
        )

    def test_all_detect_functions_importable_from_patterns(self):
        from lintlang.patterns import (  # noqa: F401
            detect_h1,
            detect_h2,
            detect_h3,
            detect_h4,
            detect_h5,
            detect_h6,
            detect_h7,
        )


class TestPatternsRegistry:
    def test_key_order(self):
        assert list(patterns.PATTERNS.keys()) == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]

    def test_entries_have_name_and_callable_detect(self):
        for spec in patterns.PATTERNS.values():
            assert "name" in spec
            assert isinstance(spec["name"], str)
            assert "detect" in spec
            assert callable(spec["detect"])


class TestIdentity:
    def test_shared_model_identity(self):
        assert patterns.Finding is models.Finding
        assert patterns.Severity is models.Severity
        assert patterns.AgentConfig is models.AgentConfig
        assert patterns.ToolDef is models.ToolDef
        assert patterns.SourceRegion is models.SourceRegion

    def test_detect_h1_identity(self):
        assert patterns.detect_h1 is h1.detect_h1

    def test_h1_private_helper_identity(self):
        assert patterns._differentia is h1._differentia
        assert patterns._meaning_terms is h1._meaning_terms
        assert patterns._word_overlap is h1._word_overlap
        assert patterns.VAGUE_WORDS is h1.VAGUE_WORDS
