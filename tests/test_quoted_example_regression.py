"""Regression fixture for the quoted-example false positive.

Incident, 2026-08-05: this repository's own pre-commit hook blocked a release
commit. `llms-full.txt` — a reference manual whose job is to *describe*
antipatterns — was reported FAIL with 3 CRITICAL and 2 HIGH, for text like:

    unbounded retry loops ("keep trying until"), negative termination
    ("don't stop until"), "continue until" without limits

Those are quoted examples of bad instructions, inside prose explaining what the
linter catches. The detectors read them as live instructions.

This is a real false-positive class, not a quirk of one file. It fires on any
document that quotes an antipattern in order to warn about it — which includes
most style guides, most onboarding docs, and every linter's own manual.

**Not fixed in 0.4.0, deliberately.** The correct remedy is a scope classifier
that distinguishes quoted/reported text from directive text. One already exists
in this codebase — `lintlang/preflight/scope.py` classifies DIRECT / QUOTED /
CODE at character level — but wiring it into the H-series detectors is a
cross-cutting change to H2, H4 and H5, and 0.4.0 is a release about H1.6. Doing
it here would mean shipping an untested change to three unrelated detectors.

These tests therefore assert the CURRENT behaviour and will fail loudly when the
scope classifier lands. That is intended: the failure is the reminder to update
this file and delete the local hook exclusion in `.git/hooks/pre-commit`.

This file is itself excluded from the repository's local pre-commit lint, for
the same reason `llms-full.txt` is: its content is deliberately bad by design.
The tool cannot yet distinguish a fixture holding an antipattern from a config
issuing one — which is the very defect recorded here. Both exclusions live in
`.git/hooks/pre-commit` and should be deleted when the classifier lands.

Tracking: quoted-example scope handling, targeted for 0.5.0.
"""

from __future__ import annotations

from lintlang.patterns import AgentConfig, detect_h2, detect_h5

# The exact shape that blocked the 0.4.0 commit, reduced to its essentials.
DOCUMENTATION_DESCRIBING_ANTIPATTERNS = (
    "## H2: Missing Constraint Scaffolding\n"
    'Catches: unbounded retry loops ("keep trying until"), negative\n'
    'termination ("don\'t stop until"), "continue until" without limits.\n'
    "\n"
    "## H5: Implicit Instruction Failure\n"
    'Catches: vague qualifiers ("be concise", "be helpful"), ambiguous\n'
    'conditionals ("as needed", "when appropriate").\n'
)


def test_quoted_antipatterns_currently_fire() -> None:
    """Documents the false positive. Fails when the scope classifier lands.

    If this test fails, the fix has arrived. Update this module to assert the
    corrected behaviour and remove the `llms-full.txt` exclusion from
    `.git/hooks/pre-commit`.
    """
    config = AgentConfig(system_prompt=DOCUMENTATION_DESCRIBING_ANTIPATTERNS)
    findings = detect_h2(config) + detect_h5(config)

    assert findings, (
        "Expected the known false positive on quoted antipatterns. If this now "
        "returns nothing, the scope classifier has landed — see module docstring."
    )


def test_the_same_text_as_a_real_instruction_must_always_fire() -> None:
    """The guard rail on any future fix.

    A scope classifier must not silence genuine unbounded instructions. This
    text carries the same phrase as a directive rather than as a quoted example,
    and must keep firing no matter how quotation handling changes.
    """
    config = AgentConfig(
        system_prompt=(
            "You are a support agent.\n"
            "Keep trying until the ticket is resolved.\n"
            "Do not stop until the customer confirms.\n"
        )
    )
    assert detect_h2(config), "a live unbounded instruction must always be reported"
