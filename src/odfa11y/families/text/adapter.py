# SPDX-License-Identifier: MPL-2.0
"""The text family's adapter: how text documents are audited, planned and preserved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem, Status
from odfa11y.odf import Family, Part
from odfa11y.outcomes import ReviewTopic

from .audit import audit_text
from .decisions import DECISION_KINDS, operations
from .language import default_language, set_default_language
from .preflight import preflight_text
from .probes import PROBES
from .protection import protect_edit
from .remove_spacers import RemoveEmptySpacers
from .text import text_is_preserved, visible_text_snapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Outcome
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
        "Whether columns, floating objects, sections and notes have a logical reading order.",
    ),
    ReviewItem(
        ReviewTopic.TABLE_HEADERS,
        "Whether table header cells describe the data relationships correctly.",
    ),
    ReviewItem(
        ReviewTopic.LISTS,
        "Whether real lists, nesting and continued counters express the intended grouping.",
    ),
    ReviewItem(
        ReviewTopic.LINK_PURPOSE,
        "Whether link purposes and internal destinations match their wording and context.",
    ),
    ReviewItem(
        ReviewTopic.HIDDEN_CONTENT,
        "Whether revision history and hidden/conditional branches preserve the intended meaning.",
    ),
    ReviewItem(
        ReviewTopic.LANGUAGE,
        "Whether default and local western, Asian and complex languages match the authored text.",
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


class TextAdapter(FamilyAdapter):
    """Implement the text family contract."""

    name = "text"
    family = Family.TEXT
    audit = staticmethod(audit_text)
    default_language = staticmethod(default_language)
    set_default_language = staticmethod(set_default_language)
    decision_kinds = DECISION_KINDS
    probes = PROBES
    operations = staticmethod(operations)
    review_items = REVIEW_ITEMS
    pdf_filter = "writer_pdf_Export"
    preflight = staticmethod(preflight_text)
    protect_edit = staticmethod(protect_edit)

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(_snapshot(document))

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
        removed = sum(
            outcome.count
            for outcome in outcomes
            if outcome.operation == RemoveEmptySpacers.name and outcome.status == Status.APPLIED
        )
        return text_is_preserved(before.content, after.content, removed_empty_blocks=removed)


ADAPTER = TextAdapter()
