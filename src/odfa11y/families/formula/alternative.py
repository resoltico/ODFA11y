# SPDX-License-Identifier: MPL-2.0
"""Set a supplied spoken formula alternative without rewriting mathematics."""

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import FormulaAlternativeAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
lazy from odfa11y.odf import OdfDocument


def edit_formula(
    document: OdfDocument, decision: Decision[FormulaAlternativeAnswer]
) -> tuple[Outcome, ...]:
    """Set a supplied spoken alternative while preserving the expression."""
    root = resolved_node(document, decision)
    value = decision.answer.alternative.strip()
    changed = root.get("alttext") != value
    if changed:
        root.set("alttext", value)
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            "Set the supplied formula alternative."
            if changed
            else "Formula alternative already matches.",
            target=decision.target_path,
            count=int(changed),
        ),
    )
