# SPDX-License-Identifier: MPL-2.0
"""Set reviewed leading row and column header boundaries in text tables."""

from odfa11y.concepts import axis_count, header_count, require_safe_boundary
from odfa11y.decisions import Decision
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal, Remedy, RemedyAction
from odfa11y.families.text.answers import TableHeadersAnswer
from odfa11y.families.text.tables.classification import TableKind, classify
from odfa11y.families.text.tables.edit import mark_axis
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


def edit_headers(
    document: OdfDocument, decision: Decision[TableHeadersAnswer]
) -> tuple[Outcome, ...]:
    """Establish header boundaries and table intent before changing the selected bands."""
    table = resolved_node(document, decision)
    answer = decision.answer
    changes = {}
    for axis, count in (("rows", answer.rows), ("columns", answer.columns)):
        if count is None:
            continue
        if count > axis_count(table, axis):
            message = f"Header {axis} must be a positive count within the table."
            raise DocumentRefusal(message)
        if header_count(table, axis) != count:
            changes[axis] = count
    require_safe_boundary(table, answer.rows, answer.columns)
    if classify(table).kind in {TableKind.LAYOUT_CANDIDATE, TableKind.AMBIGUOUS}:
        message = (
            "Table intent or header relationships remain ambiguous; "
            "establish header rows in Writer."
        )
        raise DocumentRefusal(
            message,
            remedy=Remedy(
                RemedyAction.EDIT_IN_APPLICATION,
                table.get(xml_names.TABLE_NAME) or "table",
                "Use Writer table properties to declare header rows and review the table intent.",
            ),
        )
    for axis, count in changes.items():
        mark_axis(table, axis, count)
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changes else Status.UNCHANGED,
            "Applied reviewed table headers." if changes else "Table headers already match.",
            target=decision.target_path,
            count=len(changes),
        ),
    )
