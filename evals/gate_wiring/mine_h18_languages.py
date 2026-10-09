#!/usr/bin/env python3
"""Mine/replay the frozen H1.8 KEEP cohort without altering its labels.

Full descriptions, finding identities, and the exhaustive bounded n-gram
inventory stay in .hermes/local. Committed results contain phrase aggregates.
Run from the repository with PYTHONPATH=src; no network or model is used.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from replay import LABELS, MANIFEST, ROOT, identity, read, sha, write

from lintlang.detectors.h1 import _SKILL_TRIGGER
from lintlang.detectors.lang import detect, en, es, ja, ko, normalize, tr, zh
from lintlang.parsers import parse_source, read_file_text
from lintlang.scanner import scan_file

LOCAL = ROOT / ".hermes/local/h18-language"
BASELINE = "83e8fdb"
EXTENSION_BASELINE = "d980608"
LANGUAGES = {"zh": zh, "ja": ja, "ko": ko, "tr": tr, "en": en, "es": es}
# Human-selected readable examples from the lexical inventory, not negative
# rules. Their exclusivity is verified against every row in the two cohorts.
TP_PHRASES = {
    "zh": ("最佳实践", "测试模式", "测试策略", "应用程序"),
    "ja": ("日本語翻訳が必要です", "テスト戦略", "セキュリティベストプラクティス"),
    "tr": ("kapsamlı doğrulama sistemi", "evrensel kodlama standartları", "frontend geliştirme kalıpları"),
    "en": ("Windows native desktop apps", "development for Laravel", "terminal-style screen recording"),
    "es": (),
    "ko": ("범용 코딩 표준",),
}
TOPIC_PHRASES = {
    "zh": ("专业知识", "年以上经验"),
    "ja": ("を構築します", "を生成します"),
    "tr": ("test kalıpları", "API tasarımı"),
    "en": ("best practices", "architecture patterns"),
    "es": ("patrones",),
    "ko": ("본능 기반 학습 시스템",),
}


def jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def extract() -> list[dict]:
    labels, manifest = read(LABELS), read(MANIFEST)
    if len(labels) != 972:
        raise ValueError("Expected the frozen 972-finding label file")
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    rows = []
    for row in labels:
        if row["identity"][0] != "H1.8" or row["gate_decision"] != "KEEP":
            continue
        path = Path(row["path"])
        if sha(path.read_bytes()) != expected[str(path)]:
            raise ValueError("Source differs from the frozen manifest")
        skill = parse_source(read_file_text(path), path).skill
        if skill is None:
            raise ValueError("Labeled skill no longer parses")
        description = skill.description.strip()
        if _SKILL_TRIGGER.search(description):
            raise ValueError("Frozen description already has an English trigger")
        start = path.parts.index("repos") + 1
        rows.append({**row, "description": description, "language": detect(description),
                     "source_sha256": expected[str(path)], "repository": path.parts[start],
                     "relative_path": "/".join(path.parts[start + 1:])})
    if len({row["finding_id"] for row in rows}) != 298:
        raise ValueError("Duplicate or missing finding identities")
    for label, count in (("FP", 172), ("TP", 126)):
        cohort = [row for row in rows if row["label"] == label]
        if len(cohort) != count:
            raise ValueError(f"Expected {count} {label} descriptions")
        jsonl(LOCAL / f"{label.lower()}.jsonl", cohort)
    return rows


def extract_korean() -> list[dict]:
    """Replay ko-KR records separately, including non-KEEP labels.

    The requested KEEP files have only one Korean FP. The two explicit use
    clauses live in FP / ESCALATE records from the same frozen label file;
    they must not be silently inserted into the original KEEP cohort.
    """
    labels, manifest = read(LABELS), read(MANIFEST)
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    rows = []
    for row in labels:
        if row["identity"][0] != "H1.8" or "/docs/ko-KR/skills/" not in row["path"]:
            continue
        path = Path(row["path"])
        if sha(path.read_bytes()) != expected[str(path)]:
            raise ValueError("Korean supplemental source differs from the frozen manifest")
        skill = parse_source(read_file_text(path), path).skill
        if skill is None or detect(skill.description) != "ko":
            raise ValueError("Korean supplemental skill no longer parses as Korean")
        start = path.parts.index("repos") + 1
        rows.append({**row, "description": skill.description.strip(), "language": "ko",
                     "source_sha256": expected[str(path)], "repository": path.parts[start],
                     "relative_path": "/".join(path.parts[start + 1:])})
    if len({row["finding_id"] for row in rows}) != 15:
        raise ValueError("Expected the frozen 15-record ko-KR supplemental cohort")
    if sum(row["label"] == "FP" for row in rows) != 3 or sum(row["label"] == "TP" for row in rows) != 12:
        raise ValueError("Korean supplemental labels changed")
    jsonl(LOCAL / "korean-all-labeled.jsonl", rows)
    return rows


def lexical_phrases(text: str, language: str) -> set[str]:
    """Bounded mining: word 2-4 grams or uninterrupted CJK 3-20 grams.

    Document frequency counts rows (translated/duplicate descriptions are not
    independent). No tokenizer, dictionary, or guessed translation is used.
    """
    text = text.casefold()
    if language in {"en", "tr", "es", "ko"}:
        words = re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", text)
        return {" ".join(words[i:i + n]) for n in range(2, 5) for i in range(len(words) - n + 1)}
    runs = re.findall(r"[\u3041-\u30ff\u3400-\u9fff]+", text)
    return {run[i:i + n] for run in runs for n in range(3, 21) for i in range(len(run) - n + 1)}


def occurrence(phrase: str, rows: list[dict], language: str, label: str) -> int:
    return sum(phrase.casefold() in row["description"].casefold() for row in rows
               if row["language"] == language and row["label"] == label)


def mine(rows: list[dict], korean_rows: list[dict]) -> dict:
    inventories, tables = {}, {}
    for language in sorted({row["language"] for row in rows}):
        module = LANGUAGES.get(language)
        mining_rows = korean_rows if language == "ko" else rows
        counts = {label: Counter(phrase for row in mining_rows if row["language"] == language and row["label"] == label
                                 for phrase in lexical_phrases(row["description"], language))
                  for label in ("FP", "TP")}
        inventories[language] = {
            label: [{"phrase": phrase, "rows": count} for phrase, count in sorted(counts[label].items(),
                                                                                  key=lambda item: (-item[1], item[0]))
                    if phrase not in counts[other]]
            for label, other in (("FP", "TP"), ("TP", "FP"))
        }
        mappings = []
        pairs = zip(module._MAP, module._COMPILED, strict=True) if module else ()
        for (pattern, canonical), (compiled, _) in pairs:
            matches = {label: [row for row in mining_rows if row["language"] == language and row["label"] == label
                               and compiled.search(row["description"])] for label in ("FP", "TP")}
            if not matches["FP"] or matches["TP"]:
                raise ValueError(f"Mapping is not a mined FP-only cue: {language} {pattern}")
            observed = sorted({match.group() for row in matches["FP"] for match in compiled.finditer(row["description"])})
            sources = [{key: row[key] for key in ("finding_id", "repository", "relative_path")}
                       for row in matches["FP"]]
            mappings.append({"pattern": pattern, "observed_phrases": observed, "canonical": canonical.strip(),
                             "fp_rows": len(matches["FP"]), "tp_rows": len(matches["TP"]), "fp_sources": sources})
        examples = {}
        for group, phrases, label, other in (("tp_only_examples", TP_PHRASES[language], "TP", "FP"),
                                             ("fp_only_topics_not_normalized", TOPIC_PHRASES[language], "FP", "TP")):
            examples[group] = []
            for phrase in phrases:
                count = occurrence(phrase, mining_rows, language, label)
                if not count or occurrence(phrase, mining_rows, language, other):
                    raise ValueError(f"Example is not exclusive: {language} {phrase}")
                examples[group].append({"phrase": phrase, "rows": count})
        tables[language] = {"mappings": mappings, **examples,
                            "lexical_fp_only_phrases": len(inventories[language]["FP"]),
                            "lexical_tp_only_phrases": len(inventories[language]["TP"])}
    write(LOCAL / "lexical-phrases.json", inventories)
    return tables


def invariants() -> dict:
    """Prove the only existing detector edit wraps the H1.8 regex input."""
    def baseline(path: str) -> bytes:
        return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)

    h1 = "src/lintlang/detectors/h1.py"
    original = ast.parse(baseline(h1))
    current = ast.parse((ROOT / h1).read_bytes())
    def assignments(tree):
        return {node.targets[0].id: node for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    if ast.dump(assignments(original)["_SKILL_TRIGGER"]) != ast.dump(assignments(current)["_SKILL_TRIGGER"]):
        raise ValueError("The original English trigger regex changed")

    class Unwrap(ast.NodeTransformer):
        count = 0

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Name) and node.func.id == "normalize_skill_triggers"
                    and len(node.args) == 1 and not node.keywords):
                self.count += 1
                return node.args[0]
            return self.generic_visit(node)

    unwrap = Unwrap()
    current = unwrap.visit(current)
    current.body = [node for node in current.body
                    if not (isinstance(node, ast.ImportFrom) and node.level == 1 and node.module == "lang")]
    if unwrap.count != 1 or ast.dump(original) != ast.dump(current):
        raise ValueError("An existing H1 rule changed beyond H1.8 input normalization")
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASELINE,
                                     "src/lintlang/detectors", "src/lintlang/patterns.py",
                                     "src/lintlang/scanner.py", "src/lintlang/gate"], cwd=ROOT, text=True).splitlines()
    checked = [path for path in paths if path != h1]
    for path in checked:
        if baseline(path) != (ROOT / path).read_bytes():
            raise ValueError(f"An unrelated detector/gate/scanner file changed: {path}")
    return {"baseline_commit": BASELINE, "baseline_h1_sha256": sha(baseline(h1)),
            "english_trigger_assignment_ast_unchanged": True,
            "english_trigger_pattern_sha256": hashlib.sha256(_SKILL_TRIGGER.pattern.encode()).hexdigest(),
            "existing_h1_ast_identical_after_unwrapping_normalizer": True,
            "other_detector_gate_scanner_files_byte_identical": checked}


def evaluate(rows: list[dict], output_name: str = "validation.jsonl") -> dict:
    evaluated = []
    for row in rows:
        scan = scan_file(row["path"], gate=False)
        if scan.input_error:
            raise ValueError("Corpus scan failed")
        findings = [finding for finding in scan.structural_findings if finding.code == "H1.8"]
        if len(findings) > 1:
            raise ValueError("Duplicate H1.8 finding")
        if findings and identity(row["path"], findings[0]) != identity(row["path"], row):
            raise ValueError("Retained H1.8 identity changed")
        normalized = normalize(row["description"])
        if bool(findings) != (not bool(_SKILL_TRIGGER.search(normalized))):
            raise ValueError("Actual scanner differs from normalized-trigger evaluation")
        if sha(Path(row["path"]).read_bytes()) != row["source_sha256"]:
            raise ValueError("Source changed during validation")
        evaluated.append({"finding_id": row["finding_id"], "label": row["label"], "language": row["language"],
                          "flagged_before": True, "flagged_after": bool(findings)})
    jsonl(LOCAL / output_name, evaluated)
    totals = {}
    for language in ["all", *sorted({row["language"] for row in rows})]:
        cohort = [row for row in evaluated if language == "all" or row["language"] == language]
        counts = {f"{label.lower()}_{state}": sum(row["label"] == label and row[f"flagged_{state}"] for row in cohort)
                  for label in ("FP", "TP") for state in ("before", "after")}
        counts["fp_removed"] = counts["fp_before"] - counts["fp_after"]
        counts["fp_reduction"] = counts["fp_removed"] / counts["fp_before"] if counts["fp_before"] else None
        counts["tp_retention"] = counts["tp_after"] / counts["tp_before"] if counts["tp_before"] else None
        totals[language] = counts
    return totals


def report(result: dict) -> str:
    totals = result["counts"]["all"]
    lines = ["# H1.8 language trigger mining", "",
             "Frozen 972-finding development corpus; the main replay uses the 172 FP / 126 TP KEEP cohort. "
             "Korean additionally uses the 15 labeled ko-KR H1.8 records in a separate supplemental replay. "
             "Historical/transferred and AI-review labels are preserved, not independently certified. "
             "Mining and evaluation use the same descriptions; this is a development replay, not held-out accuracy.", "",
             f"Actual scanner replay: FP **{totals['fp_before']} → {totals['fp_after']}** "
             f"({totals['fp_removed']} removed, {totals['fp_reduction']:.2%} reduction); "
             f"TP **{totals['tp_before']} → {totals['tp_after']}** ({totals['tp_retention']:.2%} retention).", "",
             "| Description language | FP raw | FP before extension | FP after | TP before | TP after |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for language, counts in result["counts"].items():
        if language != "all":
            prior = result["extension_baseline"]["counts"][language]["fp_after"]
            lines.append(f"| {language} | {counts['fp_before']} | {prior} | {counts['fp_after']} | {counts['tp_before']} | {counts['tp_after']} |")
    lines += ["", f"The extension removes {result['extension_baseline']['counts']['all']['fp_after'] - totals['fp_after']} "
              f"additional FPs from commit `{EXTENSION_BASELINE}`. "
              f"{len(result['residual_non_english_fp'])} labeled non-English FPs remain flagged; "
              "the requested all-but-a-couple release criterion is not met. "
              "Some residual descriptions lack usage clauses, and similar translated descriptions have conflicting "
              "FP/TP labels. Suppressing topics merely because they occur only in the FP group would change H1.8 semantics."]
    korean = result["korean_supplement"]["counts"]
    lines += ["", "A separate Korean replay includes all 15 labeled H1.8 records under `docs/ko-KR/skills/` "
              "in the same frozen corpus, including non-KEEP records. "
              f"FP **{korean['fp_before']} → {korean['fp_after']}**; "
              f"TP **{korean['tp_before']} → {korean['tp_after']}**. "
              "The two newly handled Korean FPs are `security-review` and `tdd-workflow`, both originally "
              "FP / ESCALATE. Their phrase was not present in the requested KEEP-only FP file. "
              "The original seven Korean TPs remain flagged. This supplemental result is not a 38-FP Korean replay."]
    lines += ["", "Language tags come from content: kana → ja, Hangul → ko, Han → zh; Turkish spelling/ASCII cues "
              "handle Latin text. Spanish and Korean have mined normalizers. The supplied KEEP-only corpus contains "
              "one Korean FP and seven Korean TPs, rather than 38 Korean FPs. Its single FP describes a hook-based "
              "learning system without an activation clause and remains flagged. Korean's explicit use directive "
              "was mined separately from the additional labeled FP / ESCALATE descriptions. "
              "Supported languages also run the English adapter to retain cues in mixed text. "
              "Script detection cannot reliably distinguish Han-only Japanese from Chinese, "
              "or classify arbitrary Latin/mixed text. No language-detection dependency was added.", "",
              "Counts below are row/document frequencies within each language, including duplicate descriptions. "
              "FP-only does not itself establish an activation cue; topic-only discriminators remain unnormalized. "
              "TP-only phrases are descriptive patterns/translation placeholders, not negative detector rules. "
              "Generic Chinese 使用/用于, Japanese 使用した/使用して, and Turkish için are insufficient alone. "
              "English cues immediately preceded by not/never and Chinese cues immediately preceded by 不 "
              "(including intervening whitespace) are left unchanged. Japanese negative usage endings and Turkish "
              "building clauses followed immediately by kullanma/kullanmayın/kullanmayınız are also left unchanged. "
              "These are local grammar guards, not a general semantic negation analysis."]
    for language, table in result["phrases"].items():
        lines += ["", f"## {language}", "", "| Mined FP-only cue | FP rows | TP rows | Canonical English |",
                  "| --- | ---: | ---: | --- |"]
        for mapping in table["mappings"]:
            phrase = ", ".join(mapping["observed_phrases"])
            lines.append(f"| {phrase} | {mapping['fp_rows']} | {mapping['tp_rows']} | {mapping['canonical']} |")
        added = [mapping for mapping in table["mappings"] if mapping["new_in_extension"]]
        if added:
            lines += ["", "| New cue source | Finding | FP skill description |",
                      "| --- | --- | --- |"]
            for mapping in added:
                phrase = ", ".join(mapping["observed_phrases"])
                for source in mapping["fp_sources"]:
                    lines.append(f"| {phrase} | {source['finding_id']} | {source['repository']}/{source['relative_path']} |")
        if language == "ko":
            lines += ["", "This phrase table uses the separate 3-FP / 12-TP Korean cohort described above. "
                      "The single KEEP-only FP, `u-34b071729eea` "
                      "(`docs/ko-KR/skills/continuous-learning-v2/SKILL.md`), describes internal observation/learning "
                      "and a feature announcement. The generic `위한` purpose marker also occurs in six "
                      "of the original seven Korean TPs and is deliberately left unchanged."]
        lines += ["", "| Other distinguishing phrase | Group | Rows | Handling |",
                  "| --- | --- | ---: | --- |"]
        for row in table["fp_only_topics_not_normalized"]:
            lines.append(f"| {row['phrase']} | FP only | {row['rows']} | Topic; unchanged |")
        for row in table["tp_only_examples"]:
            lines.append(f"| {row['phrase']} | TP only | {row['rows']} | No activation clause; unchanged |")
    lines += ["", "## Remaining non-English FP descriptions", "",
              "These are the frozen labels, not an assertion that every description contains an activation clause.", "",
              "| Language | Finding | Skill description |", "| --- | --- | --- |"]
    for row in result["residual_non_english_fp"]:
        lines.append(f"| {row['language']} | {row['finding_id']} | {row['repository']}/{row['relative_path']} |")
    lines += ["", "## Reproduction and artifacts", "", "```bash",
              "PYTHONPATH=src python3 evals/gate_wiring/mine_h18_languages.py", "```", "",
              "Requires the existing private frozen corpus. Full tagged descriptions are saved separately in "
              "`.hermes/local/h18-language/fp.jsonl` and `tp.jsonl`. Source/finding provenance is retained. "
              "`lexical-phrases.json` contains every FP-only/TP-only 2–4 word gram (including Korean eojeol) "
              "and 3–20 character Chinese/Japanese gram from the six tagged languages; "
              "`validation.jsonl` records before/after flags by finding identity. The Korean supplemental descriptions "
              "and replay live in `korean-all-labeled.jsonl` and `korean-validation.jsonl`; "
              "the original KEEP-only files are preserved. "
              "[Aggregate receipt](h18-language-results.json) pins inputs and output files by SHA-256.", "",
              "The replay verifies every selected source against the manifest, every retained H1.8 identity, "
              "the unchanged English regex AST, and byte-identical other detector/gate/scanner files. "
              "H1's AST is unchanged after removing the new import and unwrapping the single H1.8 normalization call. "
              "Normalization is used only for the trigger check; source evidence, length thresholds, and other rules "
              "continue to use the original description.", "",
              "No push or public release is part of this work.", ""]
    return "\n".join(lines)


def main() -> None:
    checks = invariants()
    rows = extract()
    korean_rows = extract_korean()
    tables = mine(rows, korean_rows)
    counts = evaluate(rows)
    korean_counts = evaluate(korean_rows, "korean-validation.jsonl")["ko"]
    previous = json.loads(subprocess.check_output(
        ["git", "show", f"{EXTENSION_BASELINE}:evals/gate_wiring/h18-language-results.json"], cwd=ROOT,
    ))
    for name in ("fp.jsonl", "tp.jsonl"):
        if previous["cohort_sha256"][name] != sha((LOCAL / name).read_bytes()):
            raise ValueError("Extension baseline used a different labeled cohort")
    for language, table in tables.items():
        prior_pairs = {(mapping["pattern"], mapping["canonical"])
                       for mapping in previous["phrases"].get(language, {}).get("mappings", [])}
        for mapping in table["mappings"]:
            mapping["new_in_extension"] = (mapping["pattern"], mapping["canonical"]) not in prior_pairs
    flags = {row["finding_id"]: row["flagged_after"] for row in
             (json.loads(line) for line in (LOCAL / "validation.jsonl").read_text().splitlines())}
    residuals = [{key: row[key] for key in ("language", "finding_id", "repository", "relative_path")}
                 for row in rows if row["label"] == "FP" and row["language"] != "en" and flags[row["finding_id"]]]
    result = {"scope": "Frozen labeled development KEEP cohort; no held-out accuracy claim",
              "label_file_sha256": sha(LABELS.read_bytes()), "manifest_sha256": sha(MANIFEST.read_bytes()),
              "historical_seed_sha256": read(MANIFEST)["seed_sha256"], "invariants": checks,
              "counts": counts, "phrases": tables,
              "korean_supplement": {
                  "scope": "All labeled ko-KR H1.8 records in the same frozen corpus, including non-KEEP",
                  "counts": korean_counts,
                  "cohort_sha256": {name: sha((LOCAL / name).read_bytes())
                                    for name in ("korean-all-labeled.jsonl", "korean-validation.jsonl")},
              },
              "extension_baseline": {"commit": EXTENSION_BASELINE, "counts": previous["counts"]},
              "residual_non_english_fp": residuals,
              "cohort_sha256": {name: sha((LOCAL / name).read_bytes())
                                for name in ("fp.jsonl", "tp.jsonl", "lexical-phrases.json", "validation.jsonl")},
              "normalizer_sha256": {path.name: sha(path.read_bytes())
                                    for path in sorted((ROOT / "src/lintlang/detectors/lang").glob("*.py"))}}
    write(ROOT / "evals/gate_wiring/h18-language-results.json", result)
    (ROOT / "evals/gate_wiring/h18-language-mining.md").write_text(report(result), encoding="utf-8")
    print(json.dumps(counts, indent=2))
    print("Supplemental Korean:", json.dumps(korean_counts, sort_keys=True))


if __name__ == "__main__":
    main()
