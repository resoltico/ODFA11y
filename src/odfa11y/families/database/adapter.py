# SPDX-License-Identifier: MPL-2.0
"""Database declarations and opaque storage remain offline and unchanged."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.content import protected_xml
from odfa11y.odf import Family, Part, qn, select_elements
from odfa11y.outcomes import ReviewTopic

from .audit import audit_database
from .decisions import DECISION_KINDS, operations
from .descriptions import description_attributes

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    facts = [
        protected_xml(body, omitted_element_attributes=description_attributes(body))
        for body in bodies
    ]
    if document.has(Part.SETTINGS):
        tree = document.tree(Part.SETTINGS)
        settings = select_elements(tree, "//office:settings")
        if document.layout == "package":
            settings = [tree.getroot()]
        facts.extend(
            protected_xml(node, omitted_root_attributes=(qn("office", "version"),))
            for node in settings
        )
    return tuple(facts)


def _language(document: OdfDocument) -> str | None:
    del document
    return None


def _set_language(document: OdfDocument, tag: str) -> bool:
    del document, tag
    return False


class DatabaseAdapter(FamilyAdapter):
    """Implement the database family contract."""

    name = "database"
    family = Family.DATABASE
    audit = staticmethod(audit_database)
    default_language = staticmethod(_language)
    set_default_language = staticmethod(_set_language)
    decision_kinds = DECISION_KINDS
    operations = staticmethod(operations)
    review_items = (
        ReviewItem(
            ReviewTopic.DATABASE_MEANING,
            "Whether object descriptions explain queries, tables, forms and reports.",
        ),
        ReviewItem(
            ReviewTopic.PRIVACY_AND_EXECUTION,
            "Review credentials, bindings, SQL and macros offline before trusted native use.",
        ),
        ReviewItem(
            ReviewTopic.SOURCE_BOUNDARY,
            "Storage stays opaque; connections and PDF export are unsupported.",
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


ADAPTER = DatabaseAdapter()
