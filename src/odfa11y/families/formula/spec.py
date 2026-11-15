# SPDX-License-Identifier: MPL-2.0
"""Native MathML source semantics and the measured untagged Math PDF boundary."""

from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.formula.audit import audit_formula
from odfa11y.families.formula.expression import language, set_language, snapshot
from odfa11y.families.formula.kinds import DECISION_KINDS
from odfa11y.families.formula.probes import PROBES
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport, ReviewItem
from odfa11y.odf import Family
lazy from odfa11y.odf import OdfDocument


def _preservation(document: OdfDocument) -> PreservationSnapshot:
    """Capture protected meaning.

    Returns
    -------
    PreservationSnapshot
        The family-owned protected facts.

    """
    return PreservationSnapshot(snapshot(document))


SPEC = FamilySpec(
    family=Family.FORMULA,
    audit=audit_formula,
    kinds=DECISION_KINDS,
    export=PdfExport("math_pdf_Export"),
    snapshot=_preservation,
    language=LanguageTargets(language, set_language),
    review_items=(
        ReviewItem(
            ReviewTopic.MATHEMATICS,
            "Whether the spoken alternative conveys every symbol, relation and grouping correctly.",
        ),
        ReviewItem(
            ReviewTopic.LANGUAGE,
            "Whether notation and spoken language match the intended audience.",
        ),
        ReviewItem(
            ReviewTopic.EXPORT_BOUNDARY,
            "Native Math export lacks PDF tagging; source correctness is not PDF/UA conformance.",
        ),
    ),
    probes=PROBES,
)
