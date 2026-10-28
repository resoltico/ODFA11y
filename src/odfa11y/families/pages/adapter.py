# SPDX-License-Identifier: MPL-2.0
"""One semantic adapter for presentation and drawing page documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot
from odfa11y.content import page_snapshot, set_style_language, style_language

from .audit import audit_document
from .decisions import DECISION_KINDS, operations
from .profiles import DRAWING_PROFILE, PRESENTATION_PROFILE

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

    from .profiles import PageProfile


def _language(document: OdfDocument) -> str | None:
    return style_language(document, "paragraph")


def _set_language(document: OdfDocument, tag: str) -> bool:
    return set_style_language(document, tag, "paragraph")


class PagesAdapter(FamilyAdapter):
    """Apply one page contract with explicit native-family differences."""

    decision_kinds = DECISION_KINDS
    operations = staticmethod(operations)
    default_language = staticmethod(_language)
    set_default_language = staticmethod(_set_language)

    def __init__(self, profile: PageProfile) -> None:
        self.profile = profile
        self.name = profile.family.value
        self.family = profile.family
        self.pdf_filter = profile.pdf_filter
        self.review_items = profile.review_items

    def audit(self, document: OdfDocument, report: Report) -> None:
        """Inspect source semantics under the declared native-family profile."""
        audit_document(document, report, self.profile)

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected page contents.

        Returns
        -------
        PreservationSnapshot
            Words, geometry, notes, references and resource identities.

        """
        return PreservationSnapshot(page_snapshot(document))


PRESENTATION_ADAPTER = PagesAdapter(PRESENTATION_PROFILE)
DRAWING_ADAPTER = PagesAdapter(DRAWING_PROFILE)
