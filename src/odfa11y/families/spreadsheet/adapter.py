# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family's adapter: how Calc documents are audited, planned and preserved."""

from __future__ import annotations

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family

from .audit import audit_spreadsheet
from .config import parse_spreadsheet_table
from .language import default_language, set_default_language
from .snapshot import sheet_snapshot, sheets_preserved
from .template import spreadsheet_template

REVIEW_ITEMS = (
    ReviewItem("sheet names", "Whether each sheet name says what the sheet holds."),
    ReviewItem(
        "header cells",
        "Whether the first row and column labels describe the data they head, on every sheet.",
    ),
    ReviewItem("alt text", "Whether every picture's and chart's description is meaningful."),
    ReviewItem(
        "reading order",
        "Whether the order of sheets, rows and columns, and of floating objects, is logical.",
    ),
    ReviewItem(
        "hidden content",
        "Whether hidden sheets, rows and columns hold nothing a reader needs.",
    ),
    ReviewItem(
        "colour",
        "Whether colour, including conditional formatting, conveys information that is not "
        "available any other way.",
    ),
    ReviewItem(
        "layout",
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
    config_tables={"spreadsheet": parse_spreadsheet_table},
    template=spreadsheet_template,
    review_items=REVIEW_ITEMS,
    pdf_filter="calc_pdf_Export",
)
