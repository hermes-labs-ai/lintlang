# Hermeneutical Pattern Taxonomy: Language-to-Action Boundary Failures

## Core Thesis
AI agent frameworks are **language systems pretending to be engineering systems.** They expose APIs for tools, schemas, and messages, but the actual failure modes are linguistic — ambiguity, implicit inference, boundary erosion, format contracts. Most issues filed as "tool bugs" are actually hermeneutical problems.

---

## The 7 Patterns

### H1: Tool Description Ambiguity
- **User reports:** "Agent picks wrong tool"
- **Actual problem:** Tool descriptions are vague, overlapping, or under-specified
- **Root cause:** No framework validates how "disambiguatable" tool descriptions are to an LLM
- **Key repos:** langchain (128K), claude-code (71K), ollama (164K), llama_index (47K)
- **Issues found:** 8

### H2: Missing Constraint Scaffolding
- **User reports:** "Agent hallucinates / loops infinitely"
- **Actual problem:** System prompt lacks termination conditions, retry budgets, or progress checks
- **Root cause:** Frameworks assume the model will "do the right thing" re: termination. They provide max_iterations as a crude kill switch but no semantic constraint language.
- **Key repos:** crewAI (45K), autogen (55K), ollama (164K), n8n (177K)
- **Issues found:** 7

### H3: Schema-Intent Mismatch
- **User reports:** "Structured output is wrong/broken"
- **Actual problem:** Schema is syntactically valid but semantically incomplete — it cannot encode what the user actually wants
- **Root cause:** Pydantic/JSON Schema can express structure but not intent ("try harder," "fallback gracefully," "combine with tool use")
- **Key repos:** langchain (128K), pydantic-ai (15K), vercel/ai (22K), llama_index (47K)
- **Issues found:** 8

### H4: Context Boundary Erosion
- **User reports:** "Agent leaks state between tasks"
- **Actual problem:** No linguistic markers for task boundaries; messages are a flat list with no concept of "current task" vs "history"
- **Root cause:** Every context system treats messages as a flat array. None provide first-class boundary markers.
- **Key repos:** n8n (177K), pydantic-ai (15K), claude-code (71K), autogen (55K)
- **Issues found:** 7

### H5: Implicit Instruction Failure
- **User reports:** "Model doesn't follow instructions"
- **Actual problem:** Instructions assume human-level inference; model needs procedural, explicit directives
- **Root cause:** Users write instructions for humans ("don't apologize"), models need instructions for machines ("suppress any output token matching the pattern 'sorry/apologize/regret'")
- **Key repos:** claude-code (71K), ollama (164K), pydantic-ai (15K), llama_index (47K)
- **Issues found:** 7

### H6: Template Format Contract Violation
- **User reports:** "Agent broke after prompt change"
- **Actual problem:** User edited a prompt template but violated the model's expected reasoning format
- **Root cause:** Prompt templates are implicit contracts. Never made explicit, versioned, or validated. Framework upgrades and model changes silently break them.
- **Key repos:** langchain (128K), vercel/ai (22K), pydantic-ai (15K), crewAI (45K)
- **Issues found:** 7

### H7: Role Confusion
- **User reports:** "Chat history is messed up"
- **Actual problem:** System/user/assistant/tool role boundaries are malformed, duplicated, or semantically confused
- **Root cause:** Chat APIs use deceptively simple role model but real conversations require paired messages, referential integrity, model-specific requirements. No framework validates role structure holistically.
- **Key repos:** langchain (128K), ollama (164K), vercel/ai (22K), continuedev (32K)
- **Issues found:** 8

---

## Causal Chain

These patterns are not independent — they form a causal chain:

```
H1 (Tool Ambiguity) → H2 (Missing Constraints): Wrong tool + no recovery = infinite loop
H3 (Schema-Intent) → H5 (Implicit Instructions): Schema can't express intent, so users add implicit prompts
H4 (Context Erosion) → H7 (Role Confusion): Unbounded context corrupts role sequences
H6 (Format Contract) = Hidden substrate: Every other pattern ultimately manifests as a format violation
```

---

## Top 10 Showcase Issues

| Rank | Issue | Repo (Stars) | Pattern | Comments | Why It Showcases Expertise |
|------|-------|-------------|---------|----------|---------------------------|
| 1 | [#4380](https://github.com/anthropics/claude-code/issues/4380) Per-agent MCP tool filtering | claude-code (71K) | H1 | 23 | Tool description overload as language design problem |
| 2 | [#14361](https://github.com/n8n-io/n8n/issues/14361) AI Agent doesn't store tool usages | n8n (177K) | H2+H4 | 42 | Missing records create behavioral learning loop |
| 3 | [#35320](https://github.com/langchain-ai/langchain/issues/35320) structured_output drops tools | langchain (128K) | H3 | 9 | Fundamental API design where user intent is inexpressible |
| 4 | [#9796](https://github.com/anthropics/claude-code/issues/9796) Context compaction erases instructions | claude-code (71K) | H4+H5 | 16 | "Permanent" instructions need boundary markers |
| 5 | [#4495](https://github.com/crewAIInc/crewAI/issues/4495) Infinite tool-use loop | crewAI (45K) | H2 | 23 | Classic missing constraint scaffolding |
| 6 | [#1590](https://github.com/pydantic/pydantic-ai/issues/1590) Structured output + Union type | pydantic-ai (15K) | H3 | 17 | "Text reasoning + structured output" intent not encodable |
| 7 | [#22112](https://github.com/n8n-io/n8n/issues/22112) AI Agent v3.0 memory pollution | n8n (177K) | H4 | 8 | Missing boundaries cause tool outputs to pollute memory |
| 8 | [#8331](https://github.com/vercel/ai/issues/8331) System param wrong for Responses API | vercel/ai (22K) | H6 | 5 | Clean fixable format contract violation |
| 9 | [#5611](https://github.com/microsoft/autogen/issues/5611) Swarm forced handoff stuck | autogen (55K) | H2 | 7 | Model-dependent control flow needs hard constraints |
| 10 | [#12064](https://github.com/ollama/ollama/issues/12064) Tool call parsing errors | ollama (164K) | H1+H7 | 27 | Tool schemas without guardrails = unparseable output |

---

## Repo Density Rankings

| Rank | Repo | Stars | Issues Found | Dominant Patterns |
|------|------|-------|-------------|-------------------|
| 1 | langchain-ai/langchain | 128K | 14 | H1, H3, H6, H7 |
| 2 | pydantic/pydantic-ai | 15K | 9 | H3, H4, H5, H6 |
| 3 | anthropics/claude-code | 71K | 6 | H1, H4, H5 |
| 4 | vercel/ai | 22K | 6 | H3, H6, H7 |
| 5 | ollama/ollama | 164K | 5 | H1, H2, H7 |
| 6 | microsoft/autogen | 55K | 4 | H2, H4 |

---

## Total: 52 issues across 7 patterns, 13 repos, 700K+ combined stars
