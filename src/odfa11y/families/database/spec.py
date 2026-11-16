# SPDX-License-Identifier: MPL-2.0
"""Database declarations and opaque storage remain offline and unchanged."""

from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.database.audit import audit_database
from odfa11y.families.database.kinds import DECISION_KINDS
from odfa11y.families.spec import FamilySpec, ReviewItem, Unsupported
from odfa11y.odf import Family

SPEC = FamilySpec(
    family=Family.DATABASE,
    audit=audit_database,
    kinds=DECISION_KINDS,
    export=Unsupported(
        "Native PDF export is unsupported for standalone database documents; "
        "use the source application."
    ),
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
