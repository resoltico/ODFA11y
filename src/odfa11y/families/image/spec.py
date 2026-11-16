# SPDX-License-Identifier: MPL-2.0
"""Standard image source semantics with explicit unsupported native PDF export."""

from odfa11y.concepts import (
    set_style_language,
    style_language,
)
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.image.audit import audit_image
from odfa11y.families.image.kinds import DECISION_KINDS
from odfa11y.families.spec import FamilySpec, LanguageTargets, ReviewItem, Unsupported
from odfa11y.odf import Family
from odfa11y.odf.allowance import XmlChange
lazy from odfa11y.odf import OdfDocument


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> XmlChange:
    return set_style_language(document, tag, "paragraph")


SPEC = FamilySpec(
    family=Family.IMAGE,
    audit=audit_image,
    kinds=DECISION_KINDS,
    export=Unsupported(
        "Native PDF export is unsupported for standalone image documents; "
        "use the source application."
    ),
    language=LanguageTargets(_language, _set_language),
    review_items=(
        ReviewItem(
            ReviewTopic.IMAGE_MEANING,
            "Whether the alternative conveys the image's purpose and information.",
        ),
        ReviewItem(
            ReviewTopic.SOURCE_BOUNDARY,
            "Native standalone image export is unsupported; no Draw conversion is performed.",
        ),
    ),
)
