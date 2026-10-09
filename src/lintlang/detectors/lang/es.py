"""Spanish selection and concrete purpose clauses mined from the FP cohort.

Bare framework names, topic lists, methods, and a feature's implementation
purpose remain unchanged. The frozen cohort has no Spanish TPs; negative
regressions include Spanish versions of known topic-only descriptions.
"""

import re

# Source comments name the skill in docs/es/skills/ and its FP finding ID.
# More-specific clauses precede the shorter purpose/use constructions.
_MAP = (
    # deployment-patterns, u-4b6741626870
    (r"\bpreparación para producción\b", " use before production "),
    # laravel-verification, u-c94402990a58 (also Quarkus/Spring Boot verification)
    (r"\bbucle de verificación para proyectos\b", " use for project verification "),
    # quarkus-verification, u-5795109d05ad; springboot-verification, u-ffbce8109b39
    (r"\bantes del lanzamiento o PR\b", " before release or PR "),
    # golang-patterns, u-b67d581c06de (also Kotlin/Python/Rust patterns)
    (r"\bpara construir aplicaciones\b", " use for building applications "),
    # postgres-patterns, u-841b28bb74f6
    (r"\bpara optimización de consultas\b", " use for query optimization "),
    # database-migrations, u-801d10339c21
    (r"\bpara cambios de esquema\b", " use for schema changes "),
    # jpa-patterns, u-b2070448f2ce
    (r"\bpara diseño de entidades\b", " use for entity design "),
    # docker-patterns, u-83158259d3b8
    (r"\bpara desarrollo local\b", " use for local development "),
    # api-design, u-82eb68ee5ed4
    (r"\bpara APIs de producción\b", " use for production APIs "),
    # laravel-patterns, u-93db6bf71bad
    (r"\bpara aplicaciones en producción\b", " use for production applications "),
    # laravel-security, u-d5ecfaf88128; Spring Security, u-0d38fbc215d3
    (r"\bpara autenticación/autorización\b", " use for authentication/authorization "),
    # quarkus-security, u-cbf02ccc5535
    (r"\bpara autenticación\b", " use for authentication "),
    # e2e-testing, u-8054ae437e70
    (r"\bpara pruebas inestables\b", " use for flaky tests "),
    # coding-standards, u-1e3d0a84a6ff
    (r"\bpara nomenclatura\b", " use for naming "),
    # quarkus-patterns, u-7e853c3225d1
    (r"\bpara mensajería\b", " use for messaging "),
    # continuous-learning, u-a344104da112: explicit routing away from old skill
    (r"\bdirigir solicitudes de\b", " route requests for "),
    # security-review, u-90c3df5f61fc; tdd-workflow, u-1afd40108b17
    (r"\busar este skill al\b", " use this when "),
    # nextjs-turbopack, u-e838da51166e
    (r"\bcuándo usar\b", " when to use "),
    # springboot-patterns, u-1541de2ea2aa
    (r"\busar para\b", " use for "),
    # quarkus-tdd, u-71b8b4d84278; springboot-tdd, u-34a61c69e625
    (r"\busar al\b", " use when "),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), replacement) for pattern, replacement in _MAP)
# Internal punctuation in Next.js and version 3.x is not a sentence boundary.
_NEGATED = re.compile(r"\b(?:no|nunca|jamás)\b(?:(?![.!?;](?:\s|$)|\n).){0,80}$", re.IGNORECASE)


def normalize(text: str) -> str:
    """Expose observed selection clauses while retaining negated instructions."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(
            lambda match, source=text, canonical=replacement:
                match.group() if _NEGATED.search(source, max(0, match.start() - 85), match.start())
                else canonical,
            text,
        )
    return text
