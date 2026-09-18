# Research and design lineage

LintLang is an engineering evolution of Hermes Labs' work on epistemic failure
modes: concepts identified and studied in the research were adapted into bounded,
deterministic checks for defects that can be detected statically in agent
instructions and configuration before runtime.

## The research problem

[A Taxonomy of Epistemic Failure Modes in Large Language Models](https://hermes-labs.ai/research/taxonomy-of-epistemic-failure-modes),
by Rolando Bosch at Hermes Labs, investigates failures in how models handle
evidence, uncertainty, attribution, and competing instructions. These failures
are not limited to hallucination: factual content can be roughly correct while
the surrounding standards of scrutiny or confidence are distorted.

The taxonomy organizes seven observed behavioral patterns, including Constraint
Evasion and Silent Instruction Relaxation, with definitions, experimental
examples, proposed mechanisms, and limitations. It is a preprint, not a
peer-reviewed validation study. Its observations were primarily made on GPT-4o;
the paper does not establish interventions that reliably correct the modes or
claim that the categories exhaust the problem space.

The publication's concept DOI is `10.5281/zenodo.19042468`. The canonical reading
page above provides the current version record and the paper's own limitations.

## From research direction to an engineering tool

LintLang takes an upstream intervention point: inspect the instructions and
configuration before a model executes them. The research supplies a problem
framing; software requires a narrower, executable contract. A concern becomes a
static check only where recognized input structures, fixed text rules, or
extractable source patterns support a repeatable diagnosis and review action.

That adaptation changes both the object being inspected and the strength of the
claim. For example, a detector can flag selected conflicting output-format
requirements in a prompt. It cannot conclude that a model would silently relax
one of them. A schema mismatch or absent retry bound is similarly an authoring
finding, not an observed runtime outcome.

LintLang is therefore not a one-to-one implementation of the taxonomy. The
software's H1-H7 identifiers name engineering checks, not the paper's seven
behavioral categories. Python extraction, rule exemptions, severity thresholds,
and regression fixtures further define the implementable boundary. The separate
preflight capability also uses input-risk labels, not diagnoses that a model has
exhibited a research failure mode. See the [technical reference](../llms-full.txt)
for what each released check actually inspects.

## Tool Differentia and H1.6

[Tool Differentia: Relational Static Analysis for AI Agent Tool Descriptions](https://hermes-labs.ai/research/tool-differentia)
is later technical work documenting a specific implemented check, H1.6. Its
concept DOI is `10.5281/zenodo.21817243`; it is distinct from the taxonomy's DOI.

The motivating problem is relational: two tool definitions can be individually
valid yet fail to explain why an agent should select one rather than the other.
H1.6 compares analyzed terms from tool names and descriptions within one parsed
input, using a finite synonym lexicon. It distinguishes mutual nondistinction
from directional domination, where one description contributes no analyzed
terms beyond its neighbor. These are findings about that term model, not proofs
of semantic equivalence or predictions of tool selection.

The note connects this authoring problem to the broader concern that surface
compliance can miss an instruction's purpose. It explicitly does not claim to
detect the taxonomy's runtime Constraint Evasion mode. Its finite vocabulary,
local comparison scope, and unmeasured external-corpus precision and recall are
part of the contract, not details to omit from a product claim.

## Provenance is not software validation

Publication explains where the questions came from; it does not validate every
detector or prove LintLang's accuracy. Repository tests establish the particular
behavior they exercise. Bundled examples are regression fixtures, not an
independent accuracy benchmark. Runtime evaluations and domain or security
review remain separate evidence requirements.

Use [CITATION.cff](../CITATION.cff) for software and research citation metadata,
[INTENT.md](../INTENT.md) for product intent, and the
[integration guide](integrations.md#public-ecosystem-references) for public usage
and listing evidence. Neither provenance nor an ecosystem placement establishes
that an agent is production-safe.
