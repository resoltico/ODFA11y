# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family's adapter: how Calc documents are audited, planned and preserved."""

from __future__ import annotations

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family
from odfa11y.outcomes import ReviewTopic

from .audit import audit_spreadsheet
from .decisions import DECISION_KINDS, operations
from .language import default_language, set_default_language
from .snapshot import sheet_snapshot, sheets_preserved

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

ADAPTER = FamilyAdapter(
    name="spreadsheet",
    family=Family.SPREADSHEET,
    audit=audit_spreadsheet,
    default_language=default_language,
    set_default_language=set_default_language,
    snapshot=sheet_snapshot,
    preserved=sheets_preserved,
    decision_kinds=DECISION_KINDS,
    operations=operations,
    review_items=REVIEW_ITEMS,
    pdf_filter="calc_pdf_Export",
)
