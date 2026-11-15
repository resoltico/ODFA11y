# SPDX-License-Identifier: MPL-2.0
"""Database declarations and opaque storage remain offline and unchanged."""

from odfa11y.concepts import protected_xml
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.database.audit import audit_database
from odfa11y.families.database.descriptions import description_attributes
from odfa11y.families.database.kinds import DECISION_KINDS, operations
from odfa11y.families.spec import FamilyAdapter, ReviewItem
from odfa11y.odf import Family, Part, select_elements
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


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
            protected_xml(node, omitted_root_attributes=(xml_names.OFFICE_VERSION,))
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
