# SPDX-License-Identifier: MPL-2.0
"""The text family's adapter: how text documents are audited, planned and preserved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family, Part
from odfa11y.outcomes import ReviewTopic

from .audit import audit_text, style_summary
from .decisions import DECISION_KINDS, operations
from .language import default_language, set_default_language
from .link_probe import write_link_probe
from .preflight import preflight_text
from .protection import protect_edit
from .text import text_is_preserved, visible_text_snapshot

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.odf import OdfDocument

REVIEW_ITEMS = (
    ReviewItem(
        ReviewTopic.HEADINGS,
        "Whether each heading names its section and the hierarchy reflects the document.",
    ),
    ReviewItem(
        ReviewTopic.ALT_TEXT, "Whether every graphic's description is meaningful in its context."
    ),
    ReviewItem(
        ReviewTopic.READING_ORDER,
        "Whether the reading order, including footnotes and floating objects, is logical.",
    ),
    ReviewItem(
        ReviewTopic.TABLE_HEADERS,
        "Whether table header cells describe the data relationships correctly.",
    ),
    ReviewItem(
        ReviewTopic.LINK_PURPOSE,
        "Whether each link's purpose is understandable from its text and context.",
    ),
    ReviewItem(
        ReviewTopic.COLOUR,
        "Whether colour conveys information that is not available any other way.",
    ),
    ReviewItem(
        ReviewTopic.LAYOUT,
        "Whether the pages look right: typography, pagination and visual appearance.",
    ),
)


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    return visible_text_snapshot(document.tree(Part.CONTENT), document)


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    return text_is_preserved(before, after, removed_empty_blocks=removed_blocks)


def _link_probe(directory: Path) -> Path:
    """Create the text-family self-test document in an isolated directory.

    Returns
    -------
    Path
        The one-link ODF document to export.

    """
    probe = directory / "probe.odt"
    write_link_probe(probe)
    return probe


ADAPTER = FamilyAdapter(
    name="text",
    family=Family.TEXT,
    audit=audit_text,
    default_language=default_language,
    set_default_language=set_default_language,
    snapshot=_snapshot,
    preserved=_preserved,
    decision_kinds=DECISION_KINDS,
    operations=operations,
    review_items=REVIEW_ITEMS,
    pdf_filter="writer_pdf_Export",
    style_report=style_summary,
    link_probe=_link_probe,
    preflight=preflight_text,
    protect_edit=protect_edit,
)
