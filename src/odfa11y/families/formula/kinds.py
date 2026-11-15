# SPDX-License-Identifier: MPL-2.0
"""Formula alternative answers bound to the reviewed document source."""

from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import FormulaAlternativeAnswer
from odfa11y.families.formula.alternative import edit_formula
from odfa11y.families.formula.domain import FORMULA
from odfa11y.rules import registry as rules

FORMULA_ALTERNATIVE = DecisionKind(
    "formula.alternative",
    DecisionScope.TARGET,
    FormulaAlternativeAnswer,
    domain=FORMULA,
    resolves=(rules.MATH002,),
    edit=edit_formula,
)
DECISION_KINDS = (FORMULA_ALTERNATIVE,)
