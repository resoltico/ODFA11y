# SPDX-License-Identifier: MPL-2.0
"""Formula alternative answers bound to the reviewed document source."""

lazy from collections.abc import Sequence

from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import FormulaAlternativeAnswer
from odfa11y.families.formula.alternative import SetFormulaAlternative
from odfa11y.odf import Family
from odfa11y.targets import require_target
lazy from odfa11y.concepts.edits import Operation
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument

FORMULA_ALTERNATIVE = DecisionKind(
    "formula.alternative",
    DecisionScope.TARGET,
    FormulaAlternativeAnswer,
    frozenset({Family.FORMULA}),
    SetFormulaAlternative.name,
)
DECISION_KINDS = (FORMULA_ALTERNATIVE,)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Translate spoken alternatives without inferring mathematical meaning.

    Returns
    -------
    tuple[Operation, ...]
        Explicit alternative operations.

    """
    del document
    return tuple(
        SetFormulaAlternative(
            decision.answer_as(FormulaAlternativeAnswer).alternative,
            require_target(decision.target).fingerprint,
        )
        for decision in decisions
    )
