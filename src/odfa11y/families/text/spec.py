# SPDX-License-Identifier: MPL-2.0
"""The text family's adapter: how text documents are audited, planned and preserved."""

from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport, ReviewItem
from odfa11y.families.text.audit import audit_text
from odfa11y.families.text.kinds import DECISION_KINDS
from odfa11y.families.text.language import default_language, set_default_language
from odfa11y.families.text.probes import PROBES
from odfa11y.odf import Family

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


SPEC = FamilySpec(
    family=Family.TEXT,
    audit=audit_text,
    kinds=DECISION_KINDS,
    export=PdfExport("writer_pdf_Export"),
    language=LanguageTargets(default_language, set_default_language),
    review_items=REVIEW_ITEMS,
    probes=PROBES,
)
