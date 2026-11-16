# SPDX-License-Identifier: MPL-2.0
"""One semantic adapter for presentation and drawing page documents."""

from functools import partial

from odfa11y.concepts import set_style_language, style_language
from odfa11y.families.pages.audit import audit_document
from odfa11y.families.pages.kinds import DECISION_KINDS
from odfa11y.families.pages.profiles import DRAWING_PROFILE, PRESENTATION_PROFILE
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport
from odfa11y.odf.allowance import XmlChange
lazy from odfa11y.families.pages.profiles import PageProfile
lazy from odfa11y.odf import OdfDocument


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> XmlChange:
    return set_style_language(document, tag, "paragraph")


def _spec(profile: PageProfile) -> FamilySpec:
    return FamilySpec(
        profile.family,
        partial(audit_document, profile=profile),
        DECISION_KINDS,
        PdfExport(profile.pdf_filter),
        language=LanguageTargets(_language, _set_language),
        review_items=profile.review_items,
    )


PRESENTATION_SPEC = _spec(PRESENTATION_PROFILE)
DRAWING_SPEC = _spec(DRAWING_PROFILE)
