# SPDX-License-Identifier: MPL-2.0
"""Native MathML source semantics and the measured untagged Math PDF boundary."""

from __future__ import annotations

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family
from odfa11y.outcomes import ReviewTopic

from .audit import audit_formula
from .decisions import DECISION_KINDS, operations
from .expression import language, set_language, snapshot


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed: int) -> bool:
    return removed == 0 and before == after


ADAPTER = FamilyAdapter(
    name="formula",
    family=Family.FORMULA,
    audit=audit_formula,
    default_language=language,
    set_default_language=set_language,
    snapshot=snapshot,
    preserved=_preserved,
    decision_kinds=DECISION_KINDS,
    operations=operations,
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
    pdf_filter="math_pdf_Export",
)
