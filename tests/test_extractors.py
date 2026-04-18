"""Tests for Python prompt extraction and pipeline detectors."""

from lintlang.extractors import (
    ExtractionResult,
    ExtractedPrompt,
    ExtractedThreshold,
    detect_scaffold_in_code,
    detect_uncalibrated_thresholds,
    extract_from_python,
    extracted_prompts_to_configs,
)
from lintlang.patterns import Severity
from lintlang.scanner import scan_python_file


class TestPromptExtraction:
    """Test extraction of LLM prompts from Python source code."""

    def test_simple_prompt_detected(self):
        source = '''
SYSTEM_PROMPT = """You are a helpful assistant. Analyze the user message
and respond with a structured JSON output containing your analysis."""
'''
        result = extract_from_python(source)
        assert len(result.prompts) >= 1
        assert any("you are" in p.text.lower() for p in result.prompts)

    def test_short_strings_ignored(self):
        source = '''
x = "hello world"
y = "short"
name = "not a prompt"
'''
        result = extract_from_python(source)
        assert len(result.prompts) == 0

    def test_non_prompt_long_string_ignored(self):
        source = '''
LICENSE = """MIT License. Copyright 2024 Example Corp. All rights reserved.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files, to deal in the Software."""
'''
        result = extract_from_python(source)
        assert len(result.prompts) == 0

    def test_react_scaffold_detected(self):
        source = '''
SCAFFOLD = """thought: Consider what the user is asking for.
action: Use the appropriate tool to find the answer.
observation: Review the tool output and synthesize."""
'''
        result = extract_from_python(source)
        assert len(result.prompts) >= 1
        signals = result.prompts[0].signal_matches
        assert any("ReAct" in s for s in signals)

    def test_multiple_prompts_extracted(self):
        source = '''
SYSTEM = """You are a code reviewer. Analyze the code for bugs and respond
with a JSON output listing each issue found."""

FILTER = """You are a filter agent. Respond only with 'yes' or 'no' based on
whether the user message is relevant to the current task."""
'''
        result = extract_from_python(source)
        assert len(result.prompts) >= 2

    def test_line_numbers_captured(self):
        source = '''x = 1
y = 2
PROMPT = """You are a helpful assistant.
Analyze the user message carefully.
Respond with a structured answer."""
z = 3
'''
        result = extract_from_python(source)
        assert len(result.prompts) >= 1
        prompt = result.prompts[0]
        assert prompt.line_start == 3
        assert prompt.line_end == 5

    def test_syntax_error_handled(self):
        source = "def broken(:\n  pass"
        result = extract_from_python(source)
        assert len(result.parse_errors) == 1
        assert "SyntaxError" in result.parse_errors[0]

    def test_fstring_prompt_detected(self):
        source = '''
context = "some context"
prompt = f"""You are an assistant. Analyze the following context: {context}.
Respond with a JSON output containing your analysis of the user message."""
'''
        result = extract_from_python(source)
        assert len(result.prompts) >= 1

    def test_deduplication(self):
        source = '''
A = """You are a helpful assistant. Respond with a structured JSON output
containing your detailed analysis of the user message provided."""

B = """You are a helpful assistant. Respond with a structured JSON output
containing your detailed analysis of the user message provided."""
'''
        result = extract_from_python(source)
        # Should deduplicate identical prompts
        assert len(result.prompts) == 1


class TestThresholdExtraction:
    """Test extraction of hardcoded thresholds from Python source."""

    def test_confidence_threshold_detected(self):
        source = '''
CONFIDENCE_THRESHOLD = 0.75
'''
        result = extract_from_python(source)
        assert len(result.thresholds) == 1
        assert result.thresholds[0].name == "CONFIDENCE_THRESHOLD"
        assert result.thresholds[0].value == 0.75

    def test_calibrated_threshold_has_comment(self):
        source = '''
# Calibrated on 470-question dev set
FLAGSHIP_SCORE_THRESHOLD = 0.65
'''
        result = extract_from_python(source)
        assert len(result.thresholds) == 1
        assert result.thresholds[0].has_comment is True

    def test_uncalibrated_threshold_no_comment(self):
        source = '''
min_score = 0.8
'''
        result = extract_from_python(source)
        # min_score matches _score pattern
        thresholds = [t for t in result.thresholds if t.name == "min_score"]
        if thresholds:
            assert thresholds[0].has_comment is False

    def test_non_threshold_variable_ignored(self):
        source = '''
MAX_RETRIES = 5
name = "hello"
items = [1, 2, 3]
'''
        result = extract_from_python(source)
        assert len(result.thresholds) == 0

    def test_multiple_thresholds(self):
        source = '''
FLAGSHIP_SCORE_THRESHOLD = 0.65
FLAGSHIP_GAP_THRESHOLD = 0.03
BOOST_WEIGHT = 1.5
'''
        result = extract_from_python(source)
        assert len(result.thresholds) == 3


class TestUncalibratedThresholdDetector:
    """Test P1: Uncalibrated Threshold detector."""

    def test_uncalibrated_flagged(self):
        result = ExtractionResult(thresholds=[
            ExtractedThreshold(name="confidence_threshold", value=0.75, source_file="test.py", line=10),
        ])
        findings = detect_uncalibrated_thresholds(result)
        assert len(findings) == 1
        assert findings[0].pattern_id == "P1"
        assert findings[0].severity == Severity.MEDIUM

    def test_calibrated_not_flagged(self):
        result = ExtractionResult(thresholds=[
            ExtractedThreshold(name="confidence_threshold", value=0.75, source_file="test.py", line=10, has_comment=True, comment_text="Calibrated on 470 questions"),
        ])
        findings = detect_uncalibrated_thresholds(result)
        assert len(findings) == 0

    def test_vague_calibration_flagged_low(self):
        result = ExtractionResult(thresholds=[
            ExtractedThreshold(name="confidence_threshold", value=0.75, source_file="test.py", line=10, has_comment=True, comment_text="TODO: probably need to tune this"),
        ])
        findings = detect_uncalibrated_thresholds(result)
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW


class TestEmbeddedScaffoldDetector:
    """Test P2: Embedded Scaffold detector."""

    def test_large_prompt_flagged(self):
        long_text = "You are an assistant. " * 30 + "Analyze the user message carefully."
        result = ExtractionResult(prompts=[
            ExtractedPrompt(text=long_text, source_file="pipe.py", line_start=5, line_end=15, signal_matches=["role assignment"]),
        ])
        findings = detect_scaffold_in_code(result)
        assert len(findings) == 1
        assert findings[0].pattern_id == "P2"
        assert findings[0].severity == Severity.MEDIUM

    def test_medium_prompt_flagged_low(self):
        medium_text = "You are an assistant. " * 12 + "Respond with analysis."
        result = ExtractionResult(prompts=[
            ExtractedPrompt(text=medium_text, source_file="pipe.py", line_start=5, line_end=8, signal_matches=["role assignment"]),
        ])
        findings = detect_scaffold_in_code(result)
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW

    def test_short_prompt_not_flagged(self):
        short_text = "You are an assistant. Respond briefly."
        result = ExtractionResult(prompts=[
            ExtractedPrompt(text=short_text, source_file="pipe.py", line_start=5, line_end=5, signal_matches=["role assignment"]),
        ])
        findings = detect_scaffold_in_code(result)
        assert len(findings) == 0


class TestExtractedPromptsToConfigs:
    """Test the bridge from extracted prompts to AgentConfig."""

    def test_converts_to_agent_configs(self):
        result = ExtractionResult(prompts=[
            ExtractedPrompt(text="You are a helpful assistant.", source_file="test.py", line_start=5, line_end=5, signal_matches=["role assignment"]),
        ])
        configs = extracted_prompts_to_configs(result)
        assert len(configs) == 1
        assert configs[0].system_prompt == "You are a helpful assistant."
        assert "test.py" in configs[0].source_file

    def test_empty_extraction(self):
        result = ExtractionResult()
        configs = extracted_prompts_to_configs(result)
        assert len(configs) == 0


class TestScanPythonFile:
    """Integration tests for scan_python_file."""

    def test_scan_python_with_prompt_and_threshold(self, tmp_path):
        py_file = tmp_path / "pipeline.py"
        py_file.write_text('''
CONFIDENCE_THRESHOLD = 0.75

SYSTEM_PROMPT = """You are a data analysis assistant.
Be concise and helpful. Use common sense when analyzing data.
Don't apologize. Never guess. Avoid speculation.
Respond in JSON format with your analysis of the user message.
If the task fails, keep trying until it works.
Remember everything from the conversation history.
Use all conversation history to improve answers.
Also respond in markdown when appropriate. XML is acceptable too.
More instructions follow below for context.
Rule one. Rule two. Rule three. Rule four.
Rule five. Rule six. Rule seven. Rule eight.
Rule nine. Rule ten. Rule eleven. Rule twelve.
"""

def run_pipeline():
    pass
''')
        result = scan_python_file(py_file)
        assert result.file == str(py_file)
        assert len(result.structural_findings) > 0
        # Should find P1 (uncalibrated threshold)
        p1_findings = [f for f in result.structural_findings if f.pattern_id == "P1"]
        assert len(p1_findings) >= 1
        # Should find prompt-level issues from H-series
        h_findings = [f for f in result.structural_findings if f.pattern_id.startswith("H")]
        assert len(h_findings) >= 1

    def test_scan_clean_python_no_prompts(self, tmp_path):
        py_file = tmp_path / "clean.py"
        py_file.write_text('''
def add(a, b):
    return a + b

MAX_RETRIES = 5
''')
        result = scan_python_file(py_file)
        assert len(result.structural_findings) == 0

    def test_scan_python_syntax_error(self, tmp_path):
        py_file = tmp_path / "broken.py"
        py_file.write_text("def broken(:\n  pass")
        result = scan_python_file(py_file)
        err_findings = [f for f in result.structural_findings if f.pattern_id == "ERR"]
        assert len(err_findings) == 1
