# SPDX-License-Identifier: MPL-2.0
"""The text family's adapter: how text documents are audited, planned and preserved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family, Part

from .audit import audit_text, style_summary
from .config import parse_text_table
from .language import default_language, set_default_language
from .template import text_template
from .text import text_is_preserved, visible_text_snapshot

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

REVIEW_ITEMS = (
    ReviewItem(
        "headings",
        "Whether each heading names its section and the hierarchy reflects the document.",
    ),
    ReviewItem("alt text", "Whether every graphic's description is meaningful in its context."),
    ReviewItem(
        "reading order",
        "Whether the reading order, including footnotes and floating objects, is logical.",
    ),
    ReviewItem(
        "table headers", "Whether table header cells describe the data relationships correctly."
    ),
    ReviewItem(
        "link purpose", "Whether each link's purpose is understandable from its text and context."
    ),
    ReviewItem("colour", "Whether colour conveys information that is not available any other way."),
    ReviewItem(
        "layout", "Whether the pages look right: typography, pagination and visual appearance."
    ),
)


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    return visible_text_snapshot(document.tree(Part.CONTENT))


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    return text_is_preserved(before, after, removed_empty_blocks=removed_blocks)


ADAPTER = FamilyAdapter(
    name="text",
    family=Family.TEXT,
    audit=audit_text,
    default_language=default_language,
    set_default_language=set_default_language,
    snapshot=_snapshot,
    preserved=_preserved,
    config_tables={"text": parse_text_table},
    template=text_template,
    review_items=REVIEW_ITEMS,
    pdf_filter="writer_pdf_Export",
    style_report=style_summary,
)
