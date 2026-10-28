# SPDX-License-Identifier: MPL-2.0
"""Formula alternative answers bound to the reviewed document source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import FormulaAlternativeAnswer
from odfa11y.odf import Family

from .alternative import SetFormulaAlternative

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument

FORMULA_ALTERNATIVE = DecisionKind(
    "formula.alternative",
    DecisionScope.DOCUMENT,
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
        SetFormulaAlternative(decision.answer_as(FormulaAlternativeAnswer).alternative)
        for decision in decisions
    )
