# SPDX-License-Identifier: MPL-2.0
"""The text family's adapter: how text documents are audited, planned and preserved."""

lazy from collections.abc import Sequence

from odfa11y.concepts.edits import Status
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.spec import FamilyAdapter, ReviewItem
from odfa11y.families.text.audit import audit_text
from odfa11y.families.text.flow import text_is_preserved, visible_text_snapshot
from odfa11y.families.text.kinds import DECISION_KINDS, operations
from odfa11y.families.text.language import default_language, set_default_language
from odfa11y.families.text.preflight import preflight_text
from odfa11y.families.text.probes import PROBES
from odfa11y.families.text.protection import protect_edit
from odfa11y.families.text.spacing.remove import RemoveEmptySpacers
from odfa11y.odf import Family, Part
lazy from odfa11y.concepts.edits import Outcome
lazy from odfa11y.odf import OdfDocument

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
