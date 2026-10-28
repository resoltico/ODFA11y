# SPDX-License-Identifier: MPL-2.0
"""Standard image source semantics with explicit unsupported native PDF export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.content import (
    normalized_graphic_tree,
    protected_xml,
    set_style_language,
    style_language,
)
from odfa11y.odf import Family, Part, qn, select_elements
from odfa11y.outcomes import ReviewTopic

from .audit import audit_image
from .decisions import DECISION_KINDS, operations

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(
        protected_xml(
            normalized_graphic_tree(document, body),
            omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
        )
        for body in bodies
    )


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> bool:
    return set_style_language(document, tag, "paragraph")


class ImageAdapter(FamilyAdapter):
    """Implement the image family contract."""

    name = "image"
    family = Family.IMAGE
    audit = staticmethod(audit_image)
    default_language = staticmethod(_language)
    set_default_language = staticmethod(_set_language)
    decision_kinds = DECISION_KINDS
    operations = staticmethod(operations)
    review_items = (
        ReviewItem(
            ReviewTopic.IMAGE_MEANING,
            "Whether the alternative conveys the image's purpose and information.",
        ),
        ReviewItem(
            ReviewTopic.SOURCE_BOUNDARY,
            "Native standalone image export is unsupported; no Draw conversion is performed.",
        ),
    )

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(_snapshot(document))


ADAPTER = ImageAdapter()
