# SPDX-License-Identifier: MPL-2.0
"""Drawing semantics and the verified native PDF boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.content import page_snapshot, set_style_language, style_language
from odfa11y.odf import Family
from odfa11y.outcomes import ReviewTopic

from .audit import audit_document
from .decisions import DECISION_KINDS, operations

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> bool:
    return set_style_language(document, tag, "paragraph")


class DrawingAdapter(FamilyAdapter):
    """Implement the drawing family contract."""

    name = "drawing"
    family = Family.GRAPHICS
    audit = staticmethod(audit_document)
    default_language = staticmethod(_language)
    set_default_language = staticmethod(_set_language)
    decision_kinds = DECISION_KINDS
    operations = staticmethod(operations)
    review_items = (
        ReviewItem(ReviewTopic.PAGE_TITLES, "Whether titles identify their pages and topics."),
        ReviewItem(
            ReviewTopic.READING_ORDER,
            "Whether the complete shape order makes sense, including groups and links.",
        ),
        ReviewItem(
            ReviewTopic.ALT_TEXT, "Whether graphic descriptions convey their meaning in context."
        ),
        ReviewItem(
            ReviewTopic.COLOUR_AND_LAYOUT,
            "Whether contrast, colour, cropping and placement preserve meaning.",
        ),
        ReviewItem(
            ReviewTopic.LAYERS_AND_ANNOTATIONS,
            "Whether visible/printed layers and annotations convey the complete diagram.",
        ),
    )
    pdf_filter = "draw_pdf_Export"

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(page_snapshot(document))


ADAPTER = DrawingAdapter()
