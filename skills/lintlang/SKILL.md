---
name: lintlang
description: Scan agent instructions, tool definitions, prompts, or agent configuration files with the LintLang CLI. Use when reviewing a named file for ambiguous or conflicting instructions, missing tool contracts, or prompt risks in a Pi session.
compatibility: Requires the lintlang command on PATH; install the Python CLI with pipx or pip if absent.
---

# LintLang in Pi

Use the installed `lintlang` CLI. This skill adds a Pi workflow; it does not
bundle or replace the scanner.

1. Check `command -v lintlang`. If missing, explain that the user can install the
   current published CLI with `pipx install lintlang` (or `python -m pip install
   lintlang` in their chosen Python environment). Do not claim a scan happened.
2. Select the specific file paths named by the user. For an unnamed repository
   check, first identify its agent instruction or configuration files, then
   state which paths you will scan. Do not silently scan an entire repository.
3. Run `lintlang scan --format json <path> [<path> ...]`. Pass paths as separate
   shell arguments, safely quoted. For prompt text without a file, check
   `lintlang scan --help`: if it lists `--stdin-filename`, pipe the exact text
   to `lintlang scan - --stdin-filename prompt.txt --format json`. Earlier
   published CLIs lack this option; ask for a file path on those installations.
   Do not put private prompt text in a shell command or persistent file.
4. Report the verdict, finding codes, file locations, and concrete repair
   suggestions. Distinguish an input error or skipped file from a clean scan.
   A `FAIL` or `REVIEW` verdict is advisory unless the user requested a gate.
   For a gate, use `--fail-on review` by default (MEDIUM or higher blocks);
   use `--fail-on fail` only when the user explicitly chooses HIGH or higher.

LintLang is a deterministic static check of the supplied content. It does not
test runtime agent behavior or prove that an instruction is safe.
