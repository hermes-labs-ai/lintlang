# DELIVERABLES — lintlang

## Log

| Date | Agent | What | Files | Output | Status | Notes |
|------|-------|------|-------|--------|--------|-------|
| 2026-03-25 | Herculit0 | v0.2.0: PASS/REVIEW/FAIL verdict system | 9 files | GitHub commit 54cc445 | ✅ COMPLETE | Breaking change: HERM score → verdict. Tested against 61 real files. |
| 2026-03-25 | Herculit0 | 4-repository audit (OpenClaw + workspace skills) | 61 files | Audit report | ✅ COMPLETE | Found CRITICAL issue in lintlang-agent SKILL.md (unbounded retry). Ready to ship. |

## v0.2.0 Summary

**Released:** 2026-03-25  
**Commit:** 54cc445  
**Tests:** 107 passing, 0.09s, ruff clean

### Changes
- ✅ Terminal output: HERM score → PASS/REVIEW/FAIL verdict
- ✅ Markdown output: verdict-centered, no score
- ✅ JSON output: verdict at top level, HERM preserved under `herm` key
- ✅ CLI: `--fail-on fail|review` for verdict-based CI gating
- ✅ API: `compute_verdict()` exported
- ✅ Scanning: .md files now included (SKILL.md was silently skipped)
- ✅ Regex: `is_prompt_like` expanded for SKILL.md format detection

### Testing
- Terminal output: ✅ verified on 4 real SKILL.md files
- JSON output: ✅ verified structure + verdicts
- `--fail-on` flag: ✅ exit codes working
- Directory scanning: ✅ 58 OpenClaw skills scanned in 0.3s
- Verdict logic: ✅ 10 dedicated tests, all passing

### Production Readiness
- Zero false positives in 61-file audit
- Actionable findings on all issues detected
- Fast execution (0.3s for 58 files)
- Backward-compatible (legacy `--fail-under` still works)

**READY TO PUSH TO PyPI**
