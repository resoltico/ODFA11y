# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family's adapter: how Calc documents are audited, planned and preserved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.odf import Family
from odfa11y.outcomes import ReviewTopic

from .audit import audit_spreadsheet
from .decisions import DECISION_KINDS, operations
from .language import default_language, set_default_language
from .probes import PROBES
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


class SpreadsheetAdapter(FamilyAdapter):
    """Implement the spreadsheet family contract."""

    name = "spreadsheet"
    family = Family.SPREADSHEET
    audit = staticmethod(audit_spreadsheet)
    default_language = staticmethod(default_language)
    set_default_language = staticmethod(set_default_language)
    decision_kinds = DECISION_KINDS
    probes = PROBES
    operations = staticmethod(operations)
    review_items = REVIEW_ITEMS
    pdf_filter = "calc_pdf_Export"

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(sheet_snapshot(document))

    @staticmethod
    def preserved(
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


ADAPTER = SpreadsheetAdapter()


if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Outcome
    from odfa11y.odf import OdfDocument
