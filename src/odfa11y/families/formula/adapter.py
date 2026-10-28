# SPDX-License-Identifier: MPL-2.0
"""Native MathML source semantics and the measured untagged Math PDF boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.odf import Family
from odfa11y.outcomes import ReviewTopic

from .audit import audit_formula
from .decisions import DECISION_KINDS, operations
from .expression import language, set_language, snapshot


class FormulaAdapter(FamilyAdapter):
    """Implement the formula family contract."""

    name = "formula"
    family = Family.FORMULA
    audit = staticmethod(audit_formula)
    default_language = staticmethod(language)
    set_default_language = staticmethod(set_language)
    decision_kinds = DECISION_KINDS
    operations = staticmethod(operations)
    review_items = (
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
    )
    pdf_filter = "math_pdf_Export"

    @staticmethod
    def snapshot(document: OdfDocument) -> PreservationSnapshot:
        """Capture protected meaning.

        Returns
        -------
        PreservationSnapshot
            The family-owned protected facts.

        """
        return PreservationSnapshot(snapshot(document))


ADAPTER = FormulaAdapter()


if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
