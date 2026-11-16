# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family's adapter: how Calc documents are audited, planned and preserved."""

from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport, ReviewItem
from odfa11y.families.spreadsheet.audit import audit_spreadsheet
from odfa11y.families.spreadsheet.kinds import DECISION_KINDS
from odfa11y.families.spreadsheet.language import default_language, set_default_language
from odfa11y.families.spreadsheet.probes import PROBES
from odfa11y.odf import Family

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


SPEC = FamilySpec(
    family=Family.SPREADSHEET,
    audit=audit_spreadsheet,
    kinds=DECISION_KINDS,
    export=PdfExport("calc_pdf_Export"),
    language=LanguageTargets(default_language, set_default_language),
    review_items=REVIEW_ITEMS,
    probes=PROBES,
)
