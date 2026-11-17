# SPDX-License-Identifier: AGPL-3.0-only
"""Set a supplied spoken formula alternative without rewriting mathematics."""

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import FormulaAlternativeAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.odf import Part
from odfa11y.odf.allowance import Allowance, Attributes
lazy from odfa11y.odf import OdfDocument


def edit_formula(document: OdfDocument, decision: Decision[FormulaAlternativeAnswer]) -> EditResult:
    """Set a supplied spoken alternative while preserving the expression."""
    root = resolved_node(document, decision)
    allowance = Allowance((Attributes(Part.CONTENT, root, frozenset({"alttext"})),))
    value = decision.answer.alternative.strip()
    changed = root.get("alttext") != value
    if changed:
        root.set("alttext", value)
    return EditResult(
        (
            Outcome(
                decision.kind.id,
                Status.APPLIED if changed else Status.UNCHANGED,
                "Set the supplied formula alternative."
                if changed
                else "Formula alternative already matches.",
                target=decision.target_path,
                count=int(changed),
            ),
        ),
        allowance,
    )
