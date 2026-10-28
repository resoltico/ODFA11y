# SPDX-License-Identifier: MPL-2.0
"""Native page-family differences: hidden content, skipped shapes and review scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.adapter import ReviewItem
from odfa11y.odf import Family, Part, qn, select_elements
from odfa11y.outcomes import ReviewTopic
from odfa11y.report import RULES

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Rule


@dataclass(frozen=True, slots=True)
class PageProfile:
    """The small set of source/export differences between Impress and Draw."""

    family: Family
    pdf_filter: str
    rule_prefix: str
    skip_presentation_shapes: bool
    hidden_content: Callable[[OdfDocument], dict[str, int]]
    review_items: tuple[ReviewItem, ...]

    def rule(self, number: int) -> Rule:
        """Resolve a family's current rule identity.

        Returns
        -------
        Rule
            The registered page concept under this family's catalogue identity.

        """
        return RULES[f"{self.rule_prefix}{number:03}"]


def hidden_pages(document: OdfDocument) -> dict[str, int]:
    """Count pages using hidden presentation styles.

    Returns
    -------
    dict[str, int]
        The hidden-page count when any are declared.

    """
    styles = {
        node.get(qn("style", "name"))
        for tree in document.distinct_trees(Part.CONTENT, Part.STYLES)
        for node in select_elements(
            tree, "//style:style[style:drawing-page-properties[@presentation:visibility='hidden']]"
        )
    }
    hidden = select_elements(document.tree(Part.CONTENT), "//draw:page")
    count = sum(page.get(qn("draw", "style-name")) in styles for page in hidden)
    return {"hidden_pages": count} if count else {}


def hidden_layers(document: OdfDocument) -> dict[str, int]:
    """Count distinct hidden or print-only layer declarations.

    Returns
    -------
    dict[str, int]
        The hidden-layer declaration count when nonzero.

    """
    count = sum(
        len(select_elements(tree, "//draw:layer[@draw:display='none' or @draw:display='printer']"))
        for tree in document.distinct_trees(Part.CONTENT, Part.STYLES)
    )
    return {"hidden_layer_declarations": count} if count else {}


COMMON_REVIEW_ITEMS = (
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
)
PRESENTATION_PROFILE = PageProfile(
    family=Family.PRESENTATION,
    pdf_filter="impress_pdf_Export",
    rule_prefix="PRES",
    skip_presentation_shapes=True,
    hidden_content=hidden_pages,
    review_items=(
        *COMMON_REVIEW_ITEMS,
        ReviewItem(
            ReviewTopic.SLIDES_AND_NOTES,
            "Whether hidden slides, notes, transitions and projected content are intentional.",
        ),
    ),
)
DRAWING_PROFILE = PageProfile(
    family=Family.DRAWING,
    pdf_filter="draw_pdf_Export",
    rule_prefix="DRAW",
    skip_presentation_shapes=False,
    hidden_content=hidden_layers,
    review_items=(
        *COMMON_REVIEW_ITEMS,
        ReviewItem(
            ReviewTopic.LAYERS_AND_ANNOTATIONS,
            "Whether visible/printed layers and annotations convey the complete diagram.",
        ),
    ),
)
