"""
Feature extraction for the optional LintLang finding gate.

This module is shared between training (with sklearn/numpy) and runtime
inference (pure Python, no dependencies).

Feature names and order are a stable contract with the bundled model.
"""

import hashlib
import math
import re
import unicodedata
from typing import Any

# --- Trigger word lexicons (multilingual) ---

# Words indicating when/how to use something (H1.8 FPs often have these)
TRIGGER_WORDS_EN = {
    'when', 'if', 'use', 'for', 'during', 'while', 'before', 'after',
    'helps with', 'useful for', 'use this', 'run this', 'activate',
    'invoke', 'trigger', 'call', 'enables', 'allows'
}

TRIGGER_WORDS_ZH = {
    '当', '如果', '使用', '用于', '适用于', '在', '时候', '之前', '之后',
    '帮助', '用来', '运行', '调用', '启用'
}

TRIGGER_WORDS_JA = {
    '場合', 'ときに', '際に', '使用', '使って', '実行', '呼び出し',
    'してください', 'する時'
}

TRIGGER_WORDS_KO = {
    '경우', '때', '사용', '호출', '실행', '활성화'
}

ALL_TRIGGER_WORDS = TRIGGER_WORDS_EN | TRIGGER_WORDS_ZH | TRIGGER_WORDS_JA | TRIGGER_WORDS_KO

# Purpose-only markers (indicates pure topic description, not usage trigger)
PURPOSE_MARKERS = {
    'patterns', 'best practices', 'conventions', 'guidelines', 'overview',
    'introduction', 'about', 'summary', 'description of'
}

# Placeholder markers
PLACEHOLDER_MARKERS = {
    'todo', 'fixme', 'xxx', 'tbd', '{{', '}}', '<%', '%>', '<...>',
    '翻訳が必要', '待翻译'
}

# Rule one-hot categories
RULE_CATEGORIES = ['H1.8', 'H4.5', 'H4', 'other']

# Basename classes
BASENAME_CLASSES = ['SKILL.md', 'AGENTS.md', 'CLAUDE.md', 'GEMINI.md',
                    'copilot-instructions.md', '.cursorrules', 'README',
                    '.py', '.json', '.yaml', '.yml', 'other']

# Path markers
TEST_MARKERS = {'test', 'tests', 'testing', 'fixtures', 'fixture',
                'examples', 'example', 'samples', 'sample', 'golden',
                'snapshot', 'testdata', 'mock', 'stub'}

LOCALE_MARKERS = {'zh-cn', 'zh-tw', 'ja-jp', 'ko-kr', 'en-us', 'en-gb',
                  'de-de', 'fr-fr', 'es-es', 'pt-br', 'locales', 'i18n', 'l10n'}

AGENT_DIR_MARKERS = {'.claude', '.agents', '.codex', '.cursor', 'skills',
                     '.github/skills'}

DOCS_DIR_MARKERS = {'docs', 'documentation', 'blog', 'wiki', 'guide', 'guides'}


def normalize_text(text: str) -> str:
    """NFKC normalize and lowercase."""
    if not text:
        return ''
    return unicodedata.normalize('NFKC', text).lower()


def stable_hash(s: str, buckets: int = 8) -> int:
    """Deterministic hash to bucket."""
    h = hashlib.blake2b(s.encode('utf-8'), digest_size=8).hexdigest()
    return int(h, 16) % buckets


def count_cjk_chars(text: str) -> int:
    """Count CJK characters."""
    count = 0
    for char in text:
        cp = ord(char)
        if (0x4E00 <= cp <= 0x9FFF or    # CJK Unified
            0x3040 <= cp <= 0x309F or    # Hiragana
            0x30A0 <= cp <= 0x30FF or    # Katakana
            0xAC00 <= cp <= 0xD7AF):     # Hangul
            count += 1
    return count


def count_trigger_words(text: str) -> int:
    """Count trigger word hits."""
    text_lower = normalize_text(text)
    count = 0
    for word in ALL_TRIGGER_WORDS:
        if word in text_lower:
            count += 1
    return count


def has_purpose_only_marker(text: str) -> bool:
    """Check if text looks like pure purpose/topic description."""
    text_lower = normalize_text(text)
    return any(marker in text_lower for marker in PURPOSE_MARKERS)


def has_placeholder_marker(text: str) -> bool:
    """Check for placeholder markers."""
    text_lower = normalize_text(text)
    return any(marker in text_lower for marker in PLACEHOLDER_MARKERS)


def has_markdown_link(text: str) -> bool:
    """Check for markdown link syntax [text](path)."""
    return bool(re.search(r'\[.+?\]\(.+?\)', text or ''))


def get_basename_class(path: str) -> str:
    """Classify file basename."""
    if not path:
        return 'other'

    basename = re.split(r'[/\\]', path)[-1].lower()

    if basename == 'skill.md':
        return 'SKILL.md'
    elif basename == 'agents.md':
        return 'AGENTS.md'
    elif basename in ('claude.md', '.claude.md'):
        return 'CLAUDE.md'
    elif basename == 'gemini.md':
        return 'GEMINI.md'
    elif basename == 'copilot-instructions.md':
        return 'copilot-instructions.md'
    elif basename in ('.cursorrules', '.cursor'):
        return '.cursorrules'
    elif basename.startswith('readme'):
        return 'README'
    elif basename.endswith('.py'):
        return '.py'
    elif basename.endswith('.json'):
        return '.json'
    elif basename.endswith(('.yaml', '.yml')):
        return '.yaml'
    else:
        return 'other'


def path_has_marker(path: str, markers: set) -> bool:
    """Check if any path component matches markers."""
    if not path:
        return False
    path_lower = path.lower()
    parts = re.split(r'[/\\]', path_lower)
    return any(part in markers for part in parts)


def has_yaml_frontmatter(text: str) -> bool:
    """Check if text has YAML frontmatter."""
    if not text:
        return False
    return text.strip().startswith('---')


def has_when_to_use_section(text: str) -> bool:
    """Check for 'When to use' style section headers."""
    patterns = [
        r'#+\s*when to use',
        r'#+\s*usage',
        r'#+\s*使用方法',
        r'#+\s*使用场景',
        r'#+\s*使い方'
    ]
    text_lower = normalize_text(text)
    return any(re.search(pattern, text_lower) for pattern in patterns)


def count_headings(text: str) -> int:
    """Count markdown headings."""
    if not text:
        return 0
    return len(re.findall(r'^#+\s', text, re.MULTILINE))


def has_tool_definition(text: str) -> bool:
    """Check for tool/function definition patterns."""
    patterns = [
        r'"type"\s*:\s*"function"',
        r'"name"\s*:\s*"[^"]+"\s*,\s*"description"',
        r'tools\s*:',
        r'functions\s*:'
    ]
    return any(re.search(pattern, text or '', re.IGNORECASE) for pattern in patterns)


def extract_features(finding: dict[str, Any]) -> dict[str, float]:
    """
    Extract feature vector from a finding.

    Args:
        finding: Dict with keys: rule, severity, pattern_name, evidence,
                 context, and optionally file_path

    Returns:
        Dict mapping feature name to float value.
    """
    features = {}

    rule = finding.get('rule', '')
    severity = finding.get('severity', '')
    pattern_name = finding.get('pattern_name', '')
    evidence = finding.get('evidence', '') or ''
    context = finding.get('context', '') or ''
    file_path = finding.get('file_path', '') or ''
    if not file_path and '-' in finding.get('id', ''):
        file_path = finding['id'].split('-', 2)[1]

    # F0: Rule Identity
    # F0.1: Rule one-hot
    for cat in RULE_CATEGORIES:
        features[f'rule_{cat}'] = 1.0 if rule == cat else 0.0
    if rule not in RULE_CATEGORIES[:-1]:  # not in known rules
        features['rule_other'] = 1.0

    # F0.2: Severity ordinal
    severity_map = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
    features['severity'] = severity_map.get(severity.lower(), 2)  # default medium

    # F0.3: Pattern name hash bucket
    features['pattern_bucket'] = stable_hash(pattern_name, 8)

    # F1: Evidence Text
    # F1.1: log(1 + len(evidence))
    features['evidence_log_len'] = math.log1p(len(evidence))

    # F1.2: Evidence empty
    features['evidence_empty'] = 1.0 if len(evidence) == 0 else 0.0

    # F1.3: CJK fraction
    total_chars = len(evidence) if evidence else 1
    cjk_count = count_cjk_chars(evidence)
    features['cjk_fraction'] = cjk_count / total_chars

    # F1.4: Trigger word count
    features['trigger_word_count'] = count_trigger_words(evidence)

    # F1.5: Purpose-only marker
    features['purpose_only'] = 1.0 if has_purpose_only_marker(evidence) else 0.0

    # F1.6: Placeholder marker
    features['placeholder'] = 1.0 if has_placeholder_marker(evidence) else 0.0

    # F1.7: Markdown link
    features['markdown_link'] = 1.0 if has_markdown_link(evidence) else 0.0

    # F2: File Path
    # F2.1: Basename class (one-hot)
    basename_class = get_basename_class(file_path)
    for cls in BASENAME_CLASSES:
        features[f'basename_{cls}'] = 1.0 if basename_class == cls else 0.0

    # F2.2: Test/fixture in path
    features['test_path'] = 1.0 if path_has_marker(file_path, TEST_MARKERS) else 0.0

    # F2.3: Locale dir
    features['locale_path'] = 1.0 if path_has_marker(file_path, LOCALE_MARKERS) else 0.0

    # F2.4: Agent-tooling dir
    features['agent_dir'] = 1.0 if path_has_marker(file_path, AGENT_DIR_MARKERS) else 0.0

    # F2.5: Docs path
    features['docs_path'] = 1.0 if path_has_marker(file_path, DOCS_DIR_MARKERS) else 0.0

    # F3: Context
    # F3.1: log(1 + len(context))
    features['context_log_len'] = math.log1p(len(context))

    # F3.2: YAML frontmatter
    features['yaml_frontmatter'] = 1.0 if has_yaml_frontmatter(context) else 0.0

    # F3.3: When to use section
    features['when_to_use_section'] = 1.0 if has_when_to_use_section(context) else 0.0

    # F3.4: Heading count
    features['heading_count'] = count_headings(context)

    # F3.5: Tool definition
    features['tool_definition'] = 1.0 if has_tool_definition(context) else 0.0

    return features


def get_feature_names() -> list[str]:
    """Return ordered list of feature names for model matrix."""
    names = []

    # F0
    for cat in RULE_CATEGORIES:
        names.append(f'rule_{cat}')
    names.extend(['severity', 'pattern_bucket'])

    # F1
    names.extend([
        'evidence_log_len', 'evidence_empty', 'cjk_fraction',
        'trigger_word_count', 'purpose_only', 'placeholder', 'markdown_link'
    ])

    # F2
    for cls in BASENAME_CLASSES:
        names.append(f'basename_{cls}')
    names.extend(['test_path', 'locale_path', 'agent_dir', 'docs_path'])

    # F3
    names.extend([
        'context_log_len', 'yaml_frontmatter', 'when_to_use_section',
        'heading_count', 'tool_definition'
    ])

    return names
