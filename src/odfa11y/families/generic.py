# SPDX-License-Identifier: MPL-2.0
"""The adapter for document kinds without a family implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.odf import body_text_snapshot
from odfa11y.outcomes import ReviewTopic
from odfa11y.report import rules

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

REVIEW_ITEMS = (
    ReviewItem(
        ReviewTopic.ALT_TEXT, "Whether every graphic's description is meaningful in its context."
    ),
    ReviewItem(ReviewTopic.READING_ORDER, "Whether the reading order of the content is logical."),
    ReviewItem(
        ReviewTopic.COLOUR,
        "Whether colour conveys information that is not available any other way.",
    ),
    ReviewItem(
        ReviewTopic.LAYOUT, "Whether the pages look right: typography and visual appearance."
    ),
)


def _audit(document: OdfDocument, report: Report) -> None:
    kind = document.kind
    label = kind.name if kind is not None else "unrecognised"
    report.add(
        rules.ODF009,
        f"No semantic audit exists for {label} documents; only package, version, metadata and "
        "schema checks ran.",
    )


class GenericAdapter(FamilyAdapter):
    """Implement the generic family contract."""

    name = "generic"
    family = None
    audit = staticmethod(_audit)
    review_items = REVIEW_ITEMS

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(body_text_snapshot(document))


GENERIC = GenericAdapter()
