# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family's adapter: how Calc documents are audited, planned and preserved."""

lazy from collections.abc import Sequence

from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.decisions.edit import Outcome
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport, ReviewItem
from odfa11y.families.spreadsheet.audit import audit_spreadsheet
from odfa11y.families.spreadsheet.kinds import DECISION_KINDS
from odfa11y.families.spreadsheet.language import default_language, set_default_language
from odfa11y.families.spreadsheet.probes import PROBES
from odfa11y.families.spreadsheet.snapshot import sheet_snapshot, sheets_preserved
from odfa11y.odf import Family
lazy from odfa11y.odf import OdfDocument

REVIEW_ITEMS = (
    ReviewItem(ReviewTopic.SHEET_NAMES, "Whether each sheet name says what the sheet holds."),
    ReviewItem(
        ReviewTopic.HEADER_CELLS,
        "Whether the first row and column labels describe the data they head, on every sheet.",
    ),
    ReviewItem(
        ReviewTopic.ALT_TEXT, "Whether every picture's and chart's description is meaningful."
    ),
    ReviewItem(
        ReviewTopic.READING_ORDER,
        "Whether the order of sheets, rows and columns, and of floating objects, is logical.",
    ),
    ReviewItem(
        ReviewTopic.HIDDEN_CONTENT,
        "Whether hidden sheets, rows and columns hold nothing a reader needs.",
    ),
    ReviewItem(
        ReviewTopic.COLOUR,
        "Whether colour, including conditional formatting, conveys information that is not "
        "available any other way.",
    ),
    ReviewItem(
        ReviewTopic.LAYOUT,
        "Whether the printed or exported pages look right: print ranges, page breaks, column "
        "widths and truncated values.",
    ),
)


def _preservation(document: OdfDocument) -> PreservationSnapshot:
    """Capture protected meaning.

    Returns
    -------
    PreservationSnapshot
        The family-owned protected facts.

    """
    return PreservationSnapshot(sheet_snapshot(document))


def _preserved(
    before: PreservationSnapshot, after: PreservationSnapshot, outcomes: Sequence[Outcome]
) -> bool:
    """Compare protected meaning using the family outcome contract.

    Returns
    -------
    bool
        Whether protected meaning survived.

    """
    del outcomes
    return sheets_preserved(before.content, after.content)


SPEC = FamilySpec(
    family=Family.SPREADSHEET,
    audit=audit_spreadsheet,
    kinds=DECISION_KINDS,
    export=PdfExport("calc_pdf_Export"),
    snapshot=_preservation,
    language=LanguageTargets(default_language, set_default_language),
    review_items=REVIEW_ITEMS,
    probes=PROBES,
    preserved=_preserved,
)
