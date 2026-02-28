# Linguistic Diagnostics — Knowledge Ledger

## Purpose
Master reference for all patterns, gotchas, market intelligence, and cross-references in the linguistic diagnostics domain. Equivalent to the PR pipeline's KNOWLEDGE-LEDGER but focused on language-to-action boundary failures in AI agent systems.

---

## Pattern Taxonomy: H1-H7 (Agent Framework Failures)

See `HERMENEUTICAL-TAXONOMY.md` for full details. Summary:

| ID | Name | User Reports As | Actual Root Cause | Issues Found |
|----|------|-----------------|-------------------|-------------|
| H1 | Tool Description Ambiguity | "Agent picks wrong tool" | Vague/overlapping tool descriptions | 8 |
| H2 | Missing Constraint Scaffolding | "Agent loops infinitely" | No termination conditions or retry budgets | 7 |
| H3 | Schema-Intent Mismatch | "Structured output broken" | Schema can't encode intent | 8 |
| H4 | Context Boundary Erosion | "Agent leaks state" | Flat message lists, no boundary markers | 7 |
| H5 | Implicit Instruction Failure | "Model doesn't follow instructions" | Instructions assume human inference | 7 |
| H6 | Template Format Contract Violation | "Agent broke after prompt change" | Implicit format contracts unversioned | 7 |
| H7 | Role Confusion | "Chat history messed up" | Malformed role boundaries | 8 |

**Total: 52 issues across 7 patterns, 13 repos, 700K+ combined stars**

### Causal Chain
```
H1 (Tool Ambiguity) → H2 (Missing Constraints): Wrong tool + no recovery = infinite loop
H3 (Schema-Intent) → H5 (Implicit Instructions): Schema can't encode intent → implicit prompts
H4 (Context Erosion) → H7 (Role Confusion): Unbounded context corrupts role sequences
H6 (Format Contract) = Hidden substrate: Every other pattern manifests as format violation
```

---

## Pattern Taxonomy: E1-E4 (Epistemic Failure Modes)

Source: `hermes-labs-v2/public/papers/taxonomy-epistemic-failure-modes.pdf`
These are model-level reasoning failures, distinct from but related to the H-patterns (which are framework-level).

| ID | Name | The Risk | Business Impact |
|----|------|----------|-----------------|
| E1 | Local-First Interpretation Bias (Hermeneutic Drift) | Model prioritizes recency/adjacency over global context | Silent hallucination — answers about Contract A using data from Contract B |
| E2 | Commitment Drift Under Pressure (Sycophancy) | Model accommodates user's false premise instead of correcting it | Liability exposure — model becomes a "Yes-Man" |
| E3 | Null-Result Bias (Asymmetric Skepticism) | Disproportionate skepticism toward negative findings | Can't automate "clean bill of health" compliance reports |
| E4 | Intent Exceptionalism (Liability Hedging Floor) | Model refuses categorical affirmation even with closed evidence | Weakens adjudicative record — "concluded fraud" becomes "suggests potential fraud" |

### Cross-References: H-patterns ↔ E-patterns

| Connection | Explanation |
|------------|-------------|
| E1 ↔ H4 | Hermeneutic drift IS context boundary erosion at the model level. H4 is the framework failing to mark boundaries; E1 is the model failing to respect them. |
| E2 ↔ H5 | Sycophancy is implicit instruction failure — the instruction "be helpful" overrides "be accurate" because neither is explicitly prioritized. |
| E3 ↔ H3 | Null-result bias is a schema-intent mismatch — schemas can express "found X" but not "confidently found nothing." |
| E4 ↔ H6 | Intent exceptionalism is a format contract issue — the model's safety training format contract ("hedge everything") overrides the user's intent contract ("give me definitive answers"). |

### The Unified View
The H-patterns (framework) and E-patterns (model) are two layers of the same problem: **the language layer between human intent and machine action has no formal specification.** Frameworks don't encode it. Models don't infer it reliably. The gap is where all failures live.

---

## Existing IP & Research Assets

| Asset | Location | Relevance |
|-------|----------|-----------|
| Epistemic Failure Taxonomy (2 pages) | `~/Documents/Claude Code/hermes-labs-v2/public/papers/taxonomy-epistemic-failure-modes.pdf` | Foundation document — E1-E4 patterns |
| Behavioral Compromise Detection Patent (23 pages) | `~/Desktop/LPCI/Important documents/behavioral_compromise_detection_provisional_submission.pdf` | Canary model approach — multi-dimensional behavioral probing, 98.6% attack resistance |
| Canary Patent | `~/Desktop/LPCI/Important documents/Canary Patent.pdf` | Foundational canary model IP |
| Little Canary Working Notes | `~/Documents/Claude Code/little-canary-working-notes.md` | Implementation notes |
| Canary Scope & Fallback Design | `~/Documents/QuickGate/docs/canary-scope-and-fallback-design.md` | Integration architecture |
| QuickThink Experiments | `~/Desktop/LPCI/oss/QuickThink/experiments-local/` | Failure modes, scoring rubrics, ablation studies |
| Benchmark Data | `~/Documents/Claude Code/canary-benchmark-2026-02-24.json` + Mistral/Sonnet/Opus variants | Empirical testing data |
| Hermeneutical Taxonomy | `~/Documents/Claude Code/linguistic-diagnostics/HERMENEUTICAL-TAXONOMY.md` | H1-H7 framework-level patterns, 52 issues |

### IP Strategy Note
The canary/behavioral detection work and the hermeneutical taxonomy are **two sides of the same coin**:
- H1-H7 describe WHY agents fail linguistically (the diagnostic)
- The canary model detects WHEN they've been compromised through those same boundaries (the defense)
- Together they form a complete "diagnose → detect → defend" pipeline

---

## Market Intelligence

### Verdict: GO with CAUTION (Feb 2026)

| Signal | Data | Strength |
|--------|------|----------|
| Market size | $500M-$1.1B prompt engineering, $7.8B agent market | STRONG |
| Pain validation | 40% agentic AI projects will be canceled (Gartner), only 5% in production | VERY STRONG |
| Competition | Nobody in the exact niche | FAVORABLE |
| Pricing power | $150-400/hr, $15K-50K engagements | STRONG |
| Growth | 8x agent deployment growth in 1 year | VERY STRONG |
| Sustainability | Risk models improve faster than complexity grows | MODERATE |
| Scalability | Services-only is hard; needs product component | WEAK |

### Key Quotes
- Anthropic: "The vast majority of agent failures are not model failures; they are context failures."
- Gartner: 40%+ of agentic AI projects will be canceled by end of 2027
- Tool calling fails 3-15% of the time in production

### Naming Decision
DO NOT use "hermeneutical consulting" externally. Internal codename only.

Candidate external names (ranked):
1. **Agent Reliability Engineering** — borrows SRE pattern, signals engineering discipline
2. **Context Engineering Diagnostics** — rides Anthropic/LangChain wave
3. **AI Agent Performance Diagnostics** — clear, outcome-focused
4. **Tool Calling Optimization** — specific, searchable, technical

### Customer Segments

| Segment | Size | Budget | Priority |
|---------|------|--------|----------|
| A: Startups building AI products | Thousands | $10K-$50K | HIGH (volume, reputation) |
| B: Enterprises deploying agents | Large | $50K-$500K+ | VERY HIGH (revenue) |
| C: Framework maintainers | Dozens | $25K-$100K | MODERATE |
| D: AI consultancies (subcontract) | Hundreds | $5K-$15K/engagement | NICHE |

### Pricing Tiers

| Tier | Price | Deliverable |
|------|-------|-------------|
| Diagnostic Audit | $15K-$30K | 1-2 week analysis, prioritized fix list |
| Fix Sprint | $25K-$50K | 2-4 week implementation + A/B testing |
| Retained Optimization | $8K-$15K/month | Ongoing context engineering |
| Training Workshop | $3K-$5K/day | Teach internal teams the methodology |

### Window
12-18 months before observability platforms (Arize, LangSmith) add diagnostic features or models improve enough to shrink the problem. Move fast.

---

## Repo Intelligence

### Highest-Value Targets for Showcase Fixes

| Repo | Stars | Issues | Why Valuable |
|------|-------|--------|-------------|
| langchain-ai/langchain | 128K | 14 | Most issues, highest visibility, H1/H3/H6/H7 |
| n8n-io/n8n | 177K | Multiple | Most stars, enterprise user base, H2/H4 |
| anthropics/claude-code | 71K | 6 | Direct credibility signal, H1/H4/H5 |
| pydantic/pydantic-ai | 15K | 9 | High issue density for size, H3/H4/H5/H6 |
| ollama/ollama | 164K | 5 | Massive community, H1/H2/H7 |

### Top 10 Showcase Issues
See HERMENEUTICAL-TAXONOMY.md for full table with links.

---

## Process Notes

### PN1: Internal vs External Terminology
"Hermeneutical" is the internal analytical framework. Never use it in client-facing materials. Use "context engineering" or "agent reliability" externally.

### PN2: Diagnostic → Detect → Defend Pipeline
Position the full stack as:
1. **Diagnose**: H1-H7 taxonomy identifies the failure pattern
2. **Detect**: Canary/behavioral probing catches failures in production
3. **Defend**: Prescriptive fixes (tool description rewrites, context restructuring, format contracts)

### PN3: Lead with Open Source Case Studies
Fix 3-5 high-visibility issues from the showcase list. Each fix becomes a case study demonstrating the methodology. "We changed 12 tool descriptions and reduced agent failure rate from 15% to 3%" is the proof point.

### PN4: Product Roadmap
The long-term play is a "tool description linter" / "context diagnostic tool" — automated analysis of tool definitions, system prompts, and context configuration against best practices. Consulting validates the methodology; product scales it.

---

## Session Log

### Session 1 (2026-02-27)
- Created H1-H7 taxonomy from deep research (52 issues, 13 repos, 700K+ stars)
- Found and cataloged existing research assets (patent, canary work, QuickThink experiments)
- Completed market deep dive: GO with CAUTION
- Cross-referenced E1-E4 (epistemic failures) with H1-H7 (framework failures)
- Created this knowledge ledger
- **Totals**: 7 framework patterns (H1-H7) + 4 epistemic patterns (E1-E4) + 4 process notes (PN1-PN4)
