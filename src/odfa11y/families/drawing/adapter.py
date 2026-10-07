# SPDX-License-Identifier: MPL-2.0
"""Drawing semantics and the verified native PDF boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.content import page_snapshot, set_style_language, style_language
from odfa11y.odf import Family

from .audit import audit_document
from .config import parse_table
from .template import template

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> bool:
    return set_style_language(document, tag, "paragraph")


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    return removed_blocks == 0 and before == after


ADAPTER = FamilyAdapter(
    name="drawing",
    family=Family.GRAPHICS,
    audit=audit_document,
    default_language=_language,
    set_default_language=_set_language,
    snapshot=page_snapshot,
    preserved=_preserved,
    config_tables={"drawing": parse_table},
    template=template,
    review_items=(
        ReviewItem("page titles", "Whether titles identify their pages and topics."),
        ReviewItem(
            "reading order",
            "Whether the complete shape order makes sense, including groups and links.",
        ),
        ReviewItem("descriptions", "Whether graphic descriptions convey their meaning in context."),
        ReviewItem(
            "colour and layout",
            "Whether contrast, colour, cropping and placement preserve meaning.",
        ),
        ReviewItem(
            "layers and annotations",
            "Whether visible/printed layers and annotations convey the complete diagram.",
        ),
    ),
    pdf_filter="draw_pdf_Export",
)
