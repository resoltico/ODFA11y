# SPDX-License-Identifier: MPL-2.0
"""Standard image source semantics with explicit unsupported native PDF export."""

from odfa11y.concepts import (
    normalized_graphic_tree,
    protected_xml,
    set_style_language,
    style_language,
)
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.image.audit import audit_image
from odfa11y.families.image.kinds import DECISION_KINDS, operations
from odfa11y.families.spec import FamilyAdapter, ReviewItem
from odfa11y.odf import Family, Part, select_elements
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(
        protected_xml(
            normalized_graphic_tree(document, body),
            omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
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
    kinds = DECISION_KINDS
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
