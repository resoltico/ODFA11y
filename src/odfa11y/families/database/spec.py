# SPDX-License-Identifier: MPL-2.0
"""Database declarations and opaque storage remain offline and unchanged."""

from odfa11y.concepts import protected_xml
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.database.audit import audit_database
from odfa11y.families.database.descriptions import description_attributes
from odfa11y.families.database.kinds import DECISION_KINDS
from odfa11y.families.spec import FamilySpec, ReviewItem, Unsupported
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


def _preservation(document: OdfDocument) -> PreservationSnapshot:
    """Capture protected meaning.

    Returns
    -------
    PreservationSnapshot
        The family-owned protected facts.

    """
    return PreservationSnapshot(_snapshot(document))


SPEC = FamilySpec(
    family=Family.DATABASE,
    audit=audit_database,
    kinds=DECISION_KINDS,
    export=Unsupported(
        "Native PDF export is unsupported for standalone database documents; "
        "use the source application."
    ),
    snapshot=_preservation,
    review_items=(
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
    ),
)
