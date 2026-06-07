# lintlang v0.3.0 — Positioning

## Target buyer
AI/ML engineering lead or senior AI engineer at a company shipping agentic products (tool-calling, RAG, multi-agent). 3-20 person AI team. Not an AI-safety researcher — an engineer shipping production agents today.

## Painful event that forces action
Agent picks wrong tools in production. Prompt drift goes undetected across sprints. A new hire edits a YAML config file and breaks a tool description — no test catches it until a user reports it. They're gate-keeping on JSON schema validity, not language quality.

## One-sentence pitch (CTO-readable in 10 seconds)
lintlang is a CI linter for your agent prompts and tool configs — same interface as a code linter, zero LLM calls, flags vague instructions before they reach runtime.

## Why existing tools don't solve it
- JSON schema validators: catch structure, not language
- LLM-based prompt evaluators: non-deterministic, expensive, not CI-safe
- Unit tests on agent behavior: test outcomes, not prompt quality; slow feedback loop
- Human review: doesn't scale across PRs

## Distribution path
1. PyPI (`pip install lintlang`) — already live at v0.2.1
2. GitHub Actions CI snippet in README — copy-paste integration
3. Show HN + AI engineering Discords
4. Direct outreach to AI leads at companies with tool-calling in production

## EU AI Act angle (Aug 2 deadline)
EU AI Act Article 13 (transparency) + Article 9 (risk management) require documented QA
on high-risk AI system inputs. A static linter producing versioned scan artifacts is the
smallest defensible step toward documented prompt QA. The Aug 2 deadline makes this a
forcing function for teams who have been deferring.

## Positioning vs competitors
| Tool | Type | Deterministic? | CI-safe? | Prompt-level? |
|------|------|----------------|----------|---------------|
| lintlang | Static linter | Yes | Yes | Yes |
| PromptLayer | Observability | No (runtime) | No | Partial |
| LangSmith | Tracing | No (runtime) | No | No |
| DSPy assertions | Runtime guard | No | No | Partial |

## Tone note
Don't lead with "zero LLM calls" as a cost argument — lead with determinism and CI-compatibility.
Cost is a secondary benefit. The primary: "you can put this in CI and the output is reproducible."
