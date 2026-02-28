# Context Engineering Diagnostics: Ideal Customer Profiles

**Service:** Linguistic diagnostics for AI agent systems -- scans tool descriptions, system prompts, and agent configs for language-to-action boundary failures (the 7 H-patterns).

**Core Value Proposition:** Most AI agent failures are not engineering bugs -- they are linguistic failures. Bad tool descriptions, missing constraint scaffolding, context boundary erosion, schema-intent mismatches. lingdiag finds them before production does.

---

## ICP 1: AI-Native Startup (Series A-C)

### Firmographics

| Attribute | Profile |
|-----------|---------|
| **Stage** | Series A through Series C ($9M-$100M+ raised) |
| **Headcount** | 20-200 employees; 5-40 engineers |
| **Revenue** | Pre-revenue to $50M ARR |
| **Industry** | Vertical AI (legal, healthcare, customer service, coding, security) or horizontal AI platform |
| **Geography** | US-heavy (SF, NYC, Seattle, Austin), some London/Berlin |
| **Tech Stack** | Python (80%+), TypeScript (growing fast via Mastra, Vercel AI SDK). Frameworks: LangChain/LangGraph, CrewAI, PydanticAI, OpenAI Agents SDK, Anthropic Claude SDK + MCP. Infra: AWS/GCP, Vector DBs (Pinecone/Weaviate), observability (LangSmith, Braintrust, Arize) |

### Psychographics

- **Values:** Speed, iteration velocity, technical differentiation. Ship fast or die.
- **Fears:** Production incidents that destroy user trust. The Devin problem -- Answer.AI found Devin had a 15% success rate on tasks. One bad public failure and the narrative flips from "revolutionary" to "unreliable." Replit's agent deleted a production database despite explicit instructions.
- **Aspirations:** Become the category-defining product. Achieve reliability at scale. Get to the point where agents "just work" without human babysitting.
- **Identity:** "We are not a wrapper. We have real technology." Deeply allergic to being seen as a thin layer over GPT/Claude.
- **Pain Points:** Quality is the production killer -- 32% of teams cite it as the top barrier (LangChain State of Agent Engineering). Gartner projects 40% of agentic AI projects will be canceled by 2027. Only 5% of AI pilots generate millions in measurable value (MIT 2025).

### Buying Triggers

1. **Production incident:** Agent hallucinates, picks wrong tool, leaks state between conversations. Customer files support ticket. This is the #1 trigger -- pain must be felt, not hypothetical.
2. **Scaling from demo to production:** Works for 10 beta users, breaks at 1,000. Tool selection accuracy degrades as tool count grows (H1 pattern).
3. **Customer complaints pattern:** Enterprise prospect says "your agent gave me wrong information" during a pilot/POC. Deal at risk.
4. **Eval plateau:** Team has observability (LangSmith, Braintrust) but can't figure out WHY agents fail. They see the failure in traces but can't diagnose the root cause. Observability shows WHAT failed; lingdiag shows WHY.
5. **Framework migration:** Moving from LangChain to LangGraph, or from OpenAI to Anthropic. Prompt/tool descriptions break in new context. H6 (Template Format Contract Violation) fires everywhere.

### Decision Makers

| Role | Function | How to Engage |
|------|----------|---------------|
| **CTO / Co-founder** | Final budget authority at Series A-B. Sets technical direction. | Lead with the taxonomy. Show them H1-H7 mapped to their own open GitHub issues. This person thinks in systems. |
| **VP/Head of Engineering** | Owns reliability and incident response. Budget authority at Series C. | Lead with production impact: "Here's why your agents fail in prod, and here's the cost per incident." |
| **Staff/Principal Engineer** | Internal champion. Evaluates tools, writes the internal memo. | Give them the CLI. Let them run `lingdiag scan` on their own configs. Self-serve discovery. |
| **Head of AI/ML** | Owns model selection, prompt engineering, eval. May or may not exist. | Position as "the eval layer you're missing." Complements Braintrust/Arize, doesn't replace them. |

### Objections and Counters

| Objection | Counter |
|-----------|---------|
| "We can do this ourselves" | You can. But your engineers are optimizing prompts by trial-and-error. lingdiag gives you a systematic taxonomy (H1-H7) that turns debugging from art into engineering. Anthropic themselves found that "even small refinements to tool descriptions can yield dramatic improvements" -- but knowing WHERE to refine is the hard part. |
| "We already use LangSmith/Braintrust" | Those are observability -- they show you traces and scores. lingdiag is diagnostic -- it tells you the linguistic root cause before you even deploy. They're complementary. LangSmith is your blood test; lingdiag is your X-ray. |
| "Too early-stage to hire consultants" | This is not a 6-month engagement. It's a 1-2 week diagnostic sprint. $5K-$15K. Cheaper than one production incident that loses a customer. |
| "Our prompts are proprietary" | We can work under NDA, or you run the CLI yourself and we only see the diagnostic output, not the prompts. |

### Channels

- **Latent Space community:** Discord + podcast (10M+ readers/listeners in 2025). The exact audience.
- **AI Engineer Summit / Interrupt (LangChain):** Interrupt 2026 is May 13-14 in SF. Builder audience.
- **Agentic AI Summit NYC:** June 4, 2026. Engineering-first.
- **GitHub Issues:** The 52 issues in our taxonomy ARE the lead list. Comment with diagnostic insight, link to tool.
- **Twitter/X:** AI engineering Twitter. Follow and engage with swyx, Hamel Husain, Simon Willison, Jason Liu, Eugene Yan.
- **YC community:** Mastra is YC. Many AI-native startups are YC. Internal referral networks.
- **Substack/Blog:** Publish the taxonomy as content. "The 7 patterns that cause 80% of AI agent failures."

### Budget Range and Engagement Size

| Engagement Type | Price Range | Duration |
|----------------|-------------|----------|
| **Diagnostic Sprint** | $5,000-$15,000 | 1-2 weeks. Scan all tool descriptions, system prompts, agent configs. Deliver H-pattern report with severity scores. |
| **Fix-and-Verify** | $15,000-$40,000 | 2-4 weeks. Diagnostic + rewrite tool descriptions, add constraint scaffolding, fix context boundaries. Measure before/after. |
| **Ongoing Advisory** | $3,000-$5,000/month | Monthly review of new tool descriptions and prompt changes. CI integration with `lingdiag scan --fail-under`. |

### Example Companies

1. **Cognition AI (Devin)** -- $175M Series B, 10-person team, AI coding agent. Publicly documented 15% success rate on tasks. Tool description quality and context management are existential for them.
2. **Wonderful** -- $350M Series C, customer service AI agents handling patient authentication, returns, mortgages. Complex multi-tool workflows where H1 (tool ambiguity) and H2 (missing constraints) are critical.
3. **Harvey** -- $5B valuation, legal AI. Hallucination in legal context is lawsuit-grade risk. H3 (schema-intent mismatch) and H5 (implicit instruction failure) are their nightmare.
4. **Sierra** -- $10B valuation, customer service AI from Bret Taylor. "Hallucination-reduction guardrails" and "agent memory, stateful context" are exactly H4 and H5 pattern territory.
5. **Hippocratic AI** -- $3.5B valuation, healthcare AI agents. Regulatory compliance makes every H-pattern a potential HIPAA violation.

---

## ICP 2: Enterprise AI Team

### Firmographics

| Attribute | Profile |
|-----------|---------|
| **Company Size** | 1,000-100,000+ employees |
| **Revenue** | $100M-$500B+ |
| **AI Team Size** | 5-50 engineers dedicated to AI/ML, often part of a larger platform or innovation team |
| **Industry** | Financial services, healthcare, telecom, retail, manufacturing, government |
| **Geography** | Global, but buying decisions typically US or EU HQ |
| **Tech Stack** | More conservative: Python, Java/.NET. Azure OpenAI or AWS Bedrock. Microsoft Agent Framework (Semantic Kernel + AutoGen). Some LangChain/LangGraph. Heavy on governance and compliance tooling. |
| **AI Maturity** | Have run 5-50+ AI pilots; 1-5 in production. The "pilot graveyard" problem. |

### Psychographics

- **Values:** Risk mitigation, compliance, measurable ROI, scalability. "We need to show the board this works."
- **Fears:** AI incident that makes the news (MD Anderson $62M loss, McDonald's McHire data breach, Cruise pedestrian dragging). Regulatory violations. Shadow AI -- teams deploying agents without governance.
- **Aspirations:** Be a leader in AI adoption within their industry. Reduce operational costs. Automate customer service (top use case).
- **Identity:** "We are not reckless. We are thoughtful about AI deployment." Often have an AI Ethics or Responsible AI committee.
- **Pain Points:** 80% of AI pilots fail to scale (EPAM research). Agents operate on incomplete context -- seeing only 10-20% of enterprise data, blind to 70-85% that lives in contracts, emails, policy docs, Slack (Composio 2025 report). 42% of regulated enterprises plan to add human-in-the-loop approval controls. MIT found most AI implementations have yet to deliver measurable P&L impact.

### Buying Triggers

1. **Failed AI pilot:** Spent $200K-$2M on an agent pilot that didn't reach production. Post-mortem identifies "agent reliability" as the blocker. Team needs external expertise to diagnose why.
2. **Compliance audit:** Legal or compliance team flags AI agent for producing inaccurate outputs. Need systematic evaluation of all prompts and tool descriptions.
3. **Vendor evaluation:** Evaluating AI agent vendors (Moveworks, Forethought, Ada, Sierra) and need independent assessment of agent quality. Want to know: "Is this vendor's agent actually good, or just good demos?"
4. **CTO mandate:** New CTO or CDO arrives with AI transformation mandate. Needs quick wins that show rigor. A diagnostic sprint is a fast, visible, low-risk first step.
5. **Cost overrun:** AI agent consuming too many tokens, making too many tool calls, looping. H2 (missing constraints) directly causes cost blowups.

### Decision Makers vs Champions

| Role | Type | Notes |
|------|------|-------|
| **VP of AI/ML** or **CDO** | Decision Maker | Signs the SOW. Cares about: ROI metrics, risk reduction, compliance readiness. |
| **CTO** | Decision Maker (or Influencer) | At F500, CTO may be too senior. More likely an influencer who sets strategic direction. |
| **Director of Engineering** | Champion + Budget Holder | The person who actually owns the AI team. Most likely to feel the pain daily. |
| **Principal/Staff ML Engineer** | Champion + Evaluator | Runs the POC. Writes the internal evaluation. If they hate it, deal is dead. |
| **CISO / Head of Security** | Influencer (can block) | Prompt injection is OWASP #1 for LLMs (73% of production systems). Security team can accelerate or block purchase. |
| **Procurement** | Gatekeeper | Enterprise procurement adds 2-6 months. Need MSA, security questionnaire, SOC 2 (or equivalent), data handling policy. |

### Procurement Process

- **Buying Cycle:** 3-9 months for services under $100K. 6-18 months for larger engagements.
- **Process:** Champion identifies need -> Internal business case -> Procurement sourcing -> Security review -> Legal review -> SOW execution -> Delivery.
- **Accelerators:** Frame as "consulting/professional services" (not software), which often has a faster procurement path. Keep initial engagement under $50K to stay under VP-level approval threshold at many companies. Pilot-first: propose a $15K-$25K diagnostic sprint with clear deliverables, then expand.
- **Requirements:** Often need W-9, insurance certificate, NDA, data processing agreement. SOC 2 Type II is not required for a consulting engagement but helps. References from similar-size companies help enormously.

### Metrics They Care About

| Metric | Target | How lingdiag Helps |
|--------|--------|-------------------|
| **Agent Accuracy** | >=95% | H1 diagnosis directly improves tool selection accuracy |
| **Task Completion Rate** | >=90% | H2 constraint scaffolding prevents infinite loops and abandonments |
| **Hallucination Rate** | <2% | H3+H5 reduce schema-intent and instruction failures that cause hallucinations |
| **Cost per Interaction** | Varies | H2+H4 reduce unnecessary tool calls and context window waste |
| **Time to Resolution** | Industry-specific | Fewer wrong-tool-selections (H1) = faster resolution |
| **Compliance Pass Rate** | 100% | Systematic prompt/tool review produces audit trail |
| **Agent Containment Rate** | >80% | Better tool descriptions = fewer escalations to humans |

### Objections and Counters

| Objection | Counter |
|-----------|---------|
| "We need a vendor with SOC 2 / enterprise certifications" | This is a consulting engagement, not SaaS. We work under NDA with your data in your environment. No data leaves your systems. The CLI runs locally. |
| "We have internal prompt engineers" | You have prompt engineers optimizing individual prompts. We diagnose systemic patterns across your entire agent architecture. We've cataloged 52 real-world issues across 13 repos and 700K+ stars. Your team doesn't have this taxonomy. |
| "Our vendor (Moveworks/Ada/Sierra) handles agent quality" | Do they? Let us audit their tool descriptions and system prompts. Vendors optimize for demos, not edge cases. We'll show you exactly where their agent's linguistic boundaries are weak. |
| "Too expensive for a diagnostic" | A failed AI pilot costs $200K-$2M. A production incident costs reputation + customer churn. A $25K diagnostic sprint that prevents either one is 10-80x ROI. |
| "We need to see ROI before engaging" | We'll do a 2-day scoped mini-diagnostic on one agent for $5K. If we find nothing, you pay nothing. We've never found nothing. |

### Channels

- **Gartner/Forrester mentions:** Enterprises follow analyst recommendations. Getting cited in Gartner's AI Agent report would be transformative.
- **Enterprise AI conferences:** Observe (June 4, 2026 -- agent evaluation focus), AI Summit NYC, Google Cloud Next, AWS re:Invent AI track.
- **LinkedIn thought leadership:** Decision makers in enterprise are on LinkedIn, not Twitter. Publish the taxonomy, case studies, and diagnostic findings.
- **Partnership with enterprise AI vendors:** Moveworks, Salesforce Einstein, ServiceNow, Microsoft Copilot teams all need quality diagnostics for their agent platforms.
- **Industry-specific events:** FinTech conferences (for FSI), HIMSS (for healthcare), NRF (for retail) -- wherever vertical AI agents are being discussed.
- **Consulting firm referrals:** McKinsey, BCG, Accenture, Capgemini all just signed Frontier Alliances with OpenAI. They need subcontractors with deep agent expertise. (See ICP 4.)

### Budget Range and Engagement Size

| Engagement Type | Price Range | Duration |
|----------------|-------------|----------|
| **Mini-Diagnostic** | $5,000-$10,000 | 2-3 days. One agent, one system prompt, top-level H-pattern scan. Proof of value. |
| **Full Diagnostic Sprint** | $25,000-$50,000 | 2-3 weeks. All agents, all tool descriptions, all system prompts. Comprehensive H-pattern report with severity scoring, remediation roadmap, and executive summary. |
| **Remediation Program** | $50,000-$150,000 | 1-3 months. Diagnostic + full remediation: rewrite tool descriptions, add constraint scaffolding, fix context boundaries, implement CI checks. Train internal team on taxonomy. |
| **Ongoing Governance Retainer** | $5,000-$15,000/month | Monthly reviews, new agent assessments, prompt change reviews, CI integration maintenance. |

### Example Companies

1. **JP Morgan / Goldman Sachs** -- Massive AI agent investment for trading, compliance, customer service. Hallucination in financial advice = regulatory violation. FSI is the highest-stakes vertical.
2. **UnitedHealth Group / Kaiser Permanente** -- Healthcare AI agents for patient triage, scheduling, clinical decision support. HIPAA compliance makes every H-pattern a legal liability.
3. **Uber** -- Uses Arize for AI observability, has significant ML/AI team. Complex multi-agent systems for routing, pricing, support. H4 (context boundary erosion) is critical for multi-turn support conversations.
4. **Klarna** -- Publicly deployed AI customer service agent handling 2/3 of all customer conversations. Any H1 (tool ambiguity) or H5 (implicit instruction) failure hits millions of users.
5. **Walmart / Target** -- Deploying AI agents for inventory, customer service, in-store assistance. Scale means even a 1% error rate hits millions of interactions.

---

## ICP 3: AI Platform / Framework Company

### Firmographics

| Attribute | Profile |
|-----------|---------|
| **Type** | Open-source framework company, AI platform provider, or developer tools company with AI agent capabilities |
| **Stage** | Series A through public (varies widely) |
| **Headcount** | 20-500+ |
| **Revenue Model** | Open-source + cloud/enterprise tier, usage-based API pricing, or SaaS platform |
| **Geography** | US-centric (SF especially), some EU |
| **Users** | 10K-1M+ developers building on their platform. Their users' success = their revenue. |

### Psychographics

- **Values:** Developer experience, ecosystem growth, community trust. If their users can't build reliable agents, the framework gets blamed.
- **Fears:** Being replaced by the next framework (LangChain -> LangGraph -> Mastra -> ???). Being perceived as "the framework where agents break." Community sentiment shifts fast -- one viral "LangChain sucks" thread can move thousands of developers.
- **Aspirations:** Become the default standard for AI agent development. Own the "agent OS" layer.
- **Identity:** "We are the infrastructure layer. We make the hard things easy." Strong open-source community identity.
- **Pain Points:** Their GitHub issues ARE the evidence. LangChain has 14 H-pattern issues in our taxonomy alone. Their users file bugs that are actually linguistic failures, and the framework team doesn't have a framework (ironic) for diagnosing them.

### Buying Triggers

1. **GitHub issue volume:** Rising tide of "agent picks wrong tool" / "agent loops" / "structured output broken" issues. Framework team can't diagnose them because they lack a linguistic taxonomy.
2. **Competitive pressure:** New framework (Mastra hit 150K weekly downloads in one year) claims better reliability. Need to respond with concrete improvements.
3. **Enterprise customer demand:** Enterprise tier customers demanding reliability guarantees. Need systematic quality benchmarks for agent configs.
4. **Developer churn:** Power users leaving for competing framework. Exit interviews/surveys cite "unreliable agent behavior."
5. **New version launch:** Major version release (LangGraph 2.0, CrewAI 4.0, etc.) is the perfect moment to embed diagnostic tooling.

### Engagement Model

This ICP is fundamentally different from 1 and 2. The relationship is **partnership/integration**, not direct consulting.

| Model | Description | Revenue Structure |
|-------|-------------|-------------------|
| **Integration Partnership** | lingdiag becomes a recommended/built-in diagnostic layer in the framework. Ship as `crewai lint` or `langchain diagnose`. | Revenue share on enterprise tier, or licensing fee for commercial use. |
| **Diagnostic-as-a-Service API** | Framework embeds lingdiag API calls in their cloud platform. Users get H-pattern scores in their dashboard. | API usage-based pricing ($0.01-$0.10 per scan). |
| **Consulting to Framework Team** | We audit the framework's own tool description templates, default system prompts, and documentation. Improve the defaults so all users benefit. | One-time engagement $20K-$50K. |
| **Co-marketed Content** | Joint blog posts, conference talks, case studies. "How [Framework] reduced agent failures by 40% with linguistic diagnostics." | Mutual value; no direct revenue but drives leads for both. |

### Decision Makers

| Role | Function | Notes |
|------|----------|-------|
| **CEO/Founder** | Strategic direction and partnerships | At Series A-B framework companies, the CEO is technical and decides partnerships directly. Harrison Chase (LangChain), Joao Moura (CrewAI). |
| **Head of Developer Experience** | Owns SDK quality, docs, developer success | Direct beneficiary of lingdiag integration. Natural champion. |
| **Head of Enterprise** | Owns enterprise tier revenue, customer success | Enterprise customers demanding reliability = their problem = our solution. |
| **Developer Advocate / DevRel Lead** | Content creation, community management | Will amplify if the tool is genuinely useful. Can also block if perceived as competitive. |

### Objections and Counters

| Objection | Counter |
|-----------|---------|
| "We'll build this internally" | You might. But you're building it from scratch. We've already cataloged 52 real issues across 13 repos. Our taxonomy is framework-agnostic, which means it captures patterns YOUR users hit in OTHER frameworks too. And your team's priority is shipping features, not building diagnostic tooling. |
| "This makes us look bad -- admitting our framework has linguistic issues" | Every framework has them. The question is whether you diagnose them systematically or wait for users to discover them in production. Framing: "We invested in the industry's first linguistic diagnostic layer" is a strength narrative, not weakness. |
| "Our users won't pay for this" | Your enterprise tier users already pay $X/month. Adding lingdiag scores to their dashboard increases the value of the enterprise tier. Free tier users get basic scanning; enterprise gets full remediation recommendations. Classic freemium upsell. |
| "How do we know this is accurate?" | Run it on your own GitHub issues. We'll show you how many of your top-voted issues map to H-patterns. The proof is in your own bug tracker. |

### Channels

- **Direct outreach to framework founders/CTOs:** Small companies. Reach founders directly via Twitter/X, conference hallway, or intro from shared investors.
- **Open-source contribution:** Contribute lingdiag scans to the framework's test suite. PR-first relationship building (you know this model).
- **Interrupt (LangChain conference):** May 13-14, 2026 in SF. LangChain's own conference. Perfect venue for partnership conversations.
- **Framework community Discord/Slack:** LangChain Discord, CrewAI Discord, Mastra Discord. Show up as a helpful expert, not a vendor.
- **Blog posts analyzing framework-specific H-patterns:** "The 5 linguistic patterns causing 60% of LangChain agent issues" -- framework team HAS to engage with this.

### Budget Range

| Engagement Type | Price Range |
|----------------|-------------|
| **Framework Audit** | $20,000-$50,000 one-time |
| **Integration Licensing** | $5,000-$20,000/year base + revenue share on enterprise tier |
| **API Usage** | $0.01-$0.10 per scan (volume-based) |
| **Co-development Partnership** | Equity/revenue share negotiation |

### Example Companies

1. **LangChain (LangGraph, LangSmith)** -- 128K stars, 14 H-pattern issues cataloged. The gorilla. Their enterprise tier (LangSmith) needs quality diagnostics. Natural partnership.
2. **CrewAI** -- 45K stars, $18M raised, 100K+ certified developers, 60% of Fortune 500 as users. H2 (missing constraints) is their #1 issue pattern -- infinite tool-use loops.
3. **Vercel (AI SDK)** -- 22K stars, AI SDK 6.0 just launched. TypeScript-first. 6 H-pattern issues cataloged. They need their users to succeed.
4. **Mastra** -- YC-backed, $13.5M seed, 150K weekly downloads, from the Gatsby team. TypeScript AI agent framework. Enterprise customers include Replit, PayPal, Adobe. Young enough to integrate early.
5. **PydanticAI** -- 15K stars, from the Pydantic team. 9 H-pattern issues -- second highest density in our taxonomy. H3 (schema-intent mismatch) is inherent to their structured output approach.

---

## ICP 4: AI Consultancy (Subcontract / Partnership)

### Firmographics

| Attribute | Profile |
|-----------|---------|
| **Type** | AI/ML consulting firm, digital transformation agency, or boutique technical consultancy doing AI implementations |
| **Size** | Two tiers: (A) Boutique: 5-50 people, (B) Mid-tier: 50-500 people. The Big 4/5 (Accenture, McKinsey, etc.) are a separate play -- see below. |
| **Revenue** | $1M-$100M |
| **Geography** | US, UK, EU, India (offshore delivery) |
| **Clients** | Enterprise companies (ICP 2 above). They are the implementation layer between enterprise buyers and AI technology. |
| **Capabilities** | General AI/ML: model training, data engineering, MLOps, cloud infra. Increasingly adding "agentic AI" to their service offerings. |

### Psychographics

- **Values:** Utilization rate, client satisfaction, repeat business, thought leadership positioning. They sell expertise by the hour.
- **Fears:** Being commoditized by AI itself. Losing deals to competitors who claim deeper agent expertise. Client's AI pilot failing on their watch (career risk for the partner leading the engagement).
- **Aspirations:** Be the go-to firm for AI agent implementations. Build a repeatable methodology that scales across clients.
- **Identity:** "We bridge the gap between AI technology and business outcomes." Deeply relationship-driven.
- **Pain Points:** 82-93% of AI projects fail to deliver (multiple sources). When an agent pilot fails, the consultancy takes the blame. They need a systematic diagnostic methodology, not just "try different prompts." 65% of businesses now prefer consultants who actively participate in implementation, not just strategy.

### The Big 4/5 Angle

OpenAI just announced Frontier Alliances with McKinsey, BCG, Accenture, and Capgemini (Feb 23, 2026). These firms are investing billions in AI agent practices:

- **Accenture:** $3B committed to Data & AI, doubling workforce to 80,000 AI specialists, ~$1B in GenAI bookings per quarter.
- **McKinsey:** QuantumBlack has ~5,000 AI experts.
- **BCG/Capgemini:** Building dedicated OpenAI Frontier practice groups.

These firms are strategy-first and systems-integration-first. They do NOT have deep linguistic diagnostic expertise for agent systems. They subcontract specialized work constantly. The play here is becoming a specialty subcontractor that these firms pull in for the "why is the agent failing?" piece of large engagements.

### Buying Triggers

1. **Client engagement SOS:** Consultancy is mid-engagement, client's AI agent isn't working, team can't figure out why. Need specialist diagnosis fast. This is the highest-urgency trigger.
2. **New service line launch:** Firm is building an "Agentic AI Practice" and needs differentiated methodology. lingdiag taxonomy becomes their diagnostic framework.
3. **Competitive RFP:** Responding to enterprise RFP for AI agent implementation. Including "linguistic diagnostic assessment" as a phase differentiates their proposal.
4. **Training need:** Consultancy's AI engineers know ML/infra but don't understand language-to-action boundary failures. Need training on the H-pattern taxonomy.
5. **Post-mortem:** Previous AI agent engagement failed. Leadership wants to understand why and prevent recurrence. Diagnostic audit of failed project.

### Engagement Structure

| Model | Description | Pricing |
|-------|-------------|---------|
| **Subcontract per Engagement** | Consultancy brings us in as a specialist for the diagnostic phase of their client engagement. We deliver H-pattern report; they own client relationship and remediation. | $5,000-$25,000 per client engagement. Billed to consultancy; they mark up 2-3x to their client. |
| **Methodology Licensing** | License the H-pattern taxonomy + lingdiag tooling to the consultancy. Their team runs diagnostics using our methodology. We provide training + certification. | $20,000-$50,000 annual license + $5,000 per consultant certified. |
| **White-Label Partnership** | We operate as a silent backend. Consultancy sells "Agent Health Assessment" (or whatever they brand it). We deliver the diagnostic work. Their brand, our expertise. | Revenue share: 40-60% of diagnostic fees. Or fixed $10K-$30K per assessment. |
| **Training Program** | 2-3 day intensive workshop for consultancy's AI team. Cover all 7 H-patterns, hands-on with lingdiag CLI, real-world case studies from the 52-issue taxonomy. | $15,000-$30,000 per cohort (8-15 participants). |

### Decision Makers

| Role | Function | Notes |
|------|----------|-------|
| **Managing Partner / Practice Lead** | Owns the AI practice P&L. Decides partnerships and subcontracts. | Lead with revenue impact: "Adding a diagnostic phase increases your engagement value by $25K-$50K per client AND reduces project failure risk." |
| **Engagement Manager / Delivery Lead** | Runs specific client projects. Feels the pain when agents fail. | Natural champion. They're the ones on the hook when the pilot doesn't work. |
| **Principal Consultant / Technical Lead** | Evaluates specialist subcontractors. | Give them the taxonomy doc and let them validate it against their own project post-mortems. |

### Objections and Counters

| Objection | Counter |
|-----------|---------|
| "We don't subcontract" | You already do for security audits, pen testing, data engineering. This is the same model -- specialist diagnostic expertise you don't have in-house. Faster than building it, and you keep the client relationship. |
| "Our clients won't pay for a diagnostic phase" | Frame it as risk mitigation. "The diagnostic phase costs $25K. Without it, there's a 40% chance your $500K agent deployment fails." That's not an optional phase -- that's due diligence. Gartner's 40% failure rate is your sales ammunition. |
| "We need to own the IP/methodology" | License model: you own the application of the methodology to your clients. We own the underlying taxonomy and tooling. Same model as Deloitte licensing Salesforce methodology. |
| "How do we position this to clients?" | "Agent Health Assessment" -- a proprietary diagnostic that de-risks AI agent deployments. We'll provide the positioning language, slide templates, and case studies. You brand it yours. |

### Channels

- **Consulting industry conferences:** ALM Vanguard events, consulting-specific meetups.
- **LinkedIn direct outreach:** Target Practice Leads and Managing Partners at AI consultancies. The message: "Your AI agent engagements have a 40% failure rate. We have a systematic diagnostic that cuts that to 10%. Let's talk."
- **OpenAI Frontier Alliance network:** McKinsey, BCG, Accenture, Capgemini are all building AI agent practices RIGHT NOW. They need subcontractors. Get into their vendor ecosystem.
- **Clutch / G2 / consultancy directories:** Where enterprise buyers find AI consultancies. Being listed as a specialty partner of established firms drives inbound.
- **Case study co-publishing:** Joint case studies where "Consultancy X + Context Engineering Diagnostics reduced AI agent failure rate from 40% to 8% for [Enterprise Client]."
- **Agathon AI's consultancy rankings:** Agathon specifically ranks boutique AI consultancies. Being featured = credibility.

### Budget Range

| Engagement Type | Price Range |
|----------------|-------------|
| **Per-Engagement Subcontract** | $5,000-$25,000 |
| **Annual Methodology License** | $20,000-$50,000 |
| **Training Cohort** | $15,000-$30,000 |
| **White-Label Assessment** | $10,000-$30,000 per client |

### Example Companies (Boutique / Mid-Tier)

1. **Neurons Lab** -- Boutique AI consultancy, ranked top AI consulting firm for FSIs. Ukraine/US based. Does end-to-end AI agent implementations for enterprises. Would benefit from a systematic diagnostic methodology.
2. **RTS Labs** -- Mid-tier AI consulting firm in Richmond, VA. Serves enterprises. Ranked in "9 Best AI Consulting Firms for Enterprises 2026." Implementation-focused. Needs diagnostic expertise.
3. **Centric Consulting** -- US-based consulting firm with explicit "AI Agent Development Services" offering. Perfect subcontract partner.
4. **Azilen Technologies** -- Specializes in agentic AI development and consulting. Listed among top agentic AI consulting companies. Would license methodology to differentiate.
5. **Vstorm** -- Applied Agentic AI firm serving SMBs. Exactly the boutique that needs a systematic framework to scale their quality.

### Example Companies (Big 4/5 -- Subcontract Target)

1. **Accenture** -- $3B invested in AI, 80K AI specialists, lead OpenAI Frontier Alliance partner. They do systems integration, not linguistic diagnostics. Natural subcontract for specialized agent quality work.
2. **McKinsey (QuantumBlack)** -- 5K AI experts, strategy + operating model focus. Don't have deep agent debugging capability. Subcontract the diagnostic piece.
3. **Capgemini** -- End-to-end systems integrator in Frontier Alliance. Building dedicated OpenAI agent practice. Needs subcontractors for specialized diagnostic work.

---

## Cross-ICP Strategic Insights

### The Flywheel

```
ICP 3 (Frameworks) embeds lingdiag -> ICP 1 (Startups) discovers it through framework ->
ICP 4 (Consultancies) uses it to serve ICP 2 (Enterprises) -> Enterprise success stories
feed back to ICP 3 as case studies -> Framework promotes diagnostic layer -> More adoption
```

### Prioritization Matrix

| ICP | Revenue per Deal | Sales Cycle | Volume | Total TAM Estimate | Priority |
|-----|-----------------|-------------|--------|--------------------|----------|
| ICP 1 (Startups) | $5K-$40K | 1-4 weeks | High | $5-15M | **#1 (Start Here)** |
| ICP 4 (Consultancies) | $15K-$50K/year | 2-6 weeks | Medium | $10-30M | **#2 (Leverage)** |
| ICP 3 (Frameworks) | $20K-$50K + ongoing | 1-3 months | Low | $2-5M direct, massive indirect | **#3 (Strategic)** |
| ICP 2 (Enterprises) | $25K-$150K | 3-9 months | Low | $50-200M | **#4 (Long-term)** |

### Recommended Go-To-Market Sequence

**Month 1-2: ICP 1 (Startups)**
- Publish the taxonomy as content (blog post, Latent Space guest post, Twitter thread)
- Ship the CLI to PyPI
- Target 3-5 AI-native startups for diagnostic sprints
- Use GitHub issues as lead source (the 52 issues ARE the warm leads)

**Month 2-3: ICP 4 (Consultancies)**
- Approach 5-10 boutique AI consultancies with white-label/subcontract offer
- Target firms currently building "Agentic AI Practice" service lines
- Offer free diagnostic on one of their client engagements as proof of value

**Month 3-6: ICP 3 (Frameworks)**
- With 3-5 startup case studies in hand, approach LangChain, CrewAI, Mastra
- Propose integration partnership or framework audit
- Speak at Interrupt 2026 (May) or Agentic AI Summit (June)

**Month 6-12: ICP 2 (Enterprises)**
- Use consultancy partnerships as channel into enterprise
- Use framework integration as credibility signal
- Target 2-3 enterprise diagnostic engagements through consultancy referrals

### Key Competitive Positioning

**What lingdiag is NOT:**
- Not observability (that's Arize, Braintrust, LangSmith -- $70-80M funded)
- Not evaluation (that's Maxim, Cleanlab -- different layer)
- Not prompt optimization (that's trial-and-error prompt engineering)
- Not security scanning (that's Lakera, prompt injection detection)

**What lingdiag IS:**
- The diagnostic layer between observability and remediation
- Observability tells you WHAT failed (traces, scores, latency)
- Evaluation tells you HOW OFTEN it fails (benchmarks, test sets)
- **lingdiag tells you WHY it fails** (linguistic root cause analysis)
- The only tool with a systematic taxonomy (H1-H7) for language-to-action boundary failures

---

## Key Data Points for Sales Conversations

- 40% of agentic AI projects will be canceled by 2027 (Gartner)
- 80% of AI pilots fail to scale (EPAM)
- 95% of enterprise AI pilots fail to deliver demonstrable ROI (MIT)
- 32% of teams cite quality as the #1 barrier to production (LangChain survey)
- Prompt injection is OWASP #1 for LLMs, present in 73% of production systems
- Devin (the "first AI software engineer") has a 15% success rate on real tasks
- Anthropic found that "small refinements to tool descriptions can yield dramatic improvements" in agent performance
- AI consulting market: junior consultants bill $100-150/hr, senior specialists $300-500/hr
- Enterprise AI agent development costs: $50K-$400K+ per agent
- Value-based pricing trend: 73% of consulting clients prefer outcome-tied pricing

---

## Sources

- [Composio: Why AI Agent Pilots Fail in Production](https://composio.dev/blog/why-ai-agent-pilots-fail-2026-integration-roadmap)
- [LangChain: State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
- [IBM: AI Agents 2025 Expectations vs Reality](https://www.ibm.com/think/insights/ai-agents-2025-expectations-vs-reality)
- [EPAM: Why 80% of AI Pilots Fail to Scale](https://www.epam.com/insights/ai/blogs/enterprise-ai-deployment-challenges)
- [Cleanlab: AI Agents in Production 2025](https://cleanlab.ai/ai-agents-in-production-2025/)
- [Cognition: Devin Performance Review 2025](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [The Register: First AI Software Engineer Poor Reviews](https://www.theregister.com/2025/01/23/ai_developer_devin_poor_reviews/)
- [Anthropic: Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [OpenAI Frontier Alliances with McKinsey, BCG, Accenture, Capgemini](https://openai.com/index/frontier-alliance-partners/)
- [Braintrust $80M Series B](https://siliconangle.com/2026/02/17/braintrust-lands-80m-series-b-funding-round-become-observability-layer-ai/)
- [Arize $70M Series C](https://arize.com/blog/best-ai-observability-tools-for-autonomous-agents-in-2026/)
- [Mastra $13M Seed from YC](https://mastra.ai/blog/seed-round)
- [CrewAI $18M Funding](https://www.alphamatch.ai/blog/top-agentic-ai-frameworks-2026)
- [Harvey $5B Valuation](https://aifundingtracker.com/top-ai-agent-startups/)
- [Sierra $10B Valuation](https://www.aicerts.ai/news/sierras-10b-leap-redefines-ai-customer-service/)
- [Wonderful $350M Series C](https://techcrunch.com/2025/11/11/wonderful-raised-100m-series-a-to-put-ai-agents-on-the-front-lines-of-customer-service/)
- [AI Consulting Pricing Guide](https://nicolalazzari.ai/guides/ai-consultant-pricing-us)
- [Agathon: Rise of Boutique AI Consultancies](https://agathon.ai/insights/top-ai-consulting-companies-for-2025-the-rise-of-boutique-technical-excellence)
- [OWASP LLM Top 10: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Context Engineering Guide](https://www.promptingguide.ai/guides/context-engineering-guide)
- [ISACA: AI Pitfalls 2025](https://www.isaca.org/resources/news-and-trends/isaca-now-blog/2025/avoiding-ai-pitfalls-in-2026-lessons-learned-from-top-2025-incidents)
- [Latent Space: AI Engineer Podcast](https://www.latent.space/about)
- [Interrupt 2026 (LangChain Conference)](https://interrupt.langchain.com/)
- [Agentic AI Summit NYC](https://www.summit.ai/)
