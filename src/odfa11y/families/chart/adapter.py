# SPDX-License-Identifier: MPL-2.0
"""Chart source assurance, using standard document metadata for its alternative."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot, ReviewItem
from odfa11y.content import protected_xml
from odfa11y.odf import Family, Part, select_elements
from odfa11y.outcomes import ReviewTopic

from .audit import audit_chart

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(protected_xml(body) for body in bodies)


class ChartAdapter(FamilyAdapter):
    """Implement the chart family contract."""

    name = "chart"
    family = Family.CHART
    audit = staticmethod(audit_chart)
    review_items = (
        ReviewItem(
            ReviewTopic.CHART_MEANING,
            "Whether the document description conveys the chart's trends, values and conclusion.",
        ),
        ReviewItem(
            ReviewTopic.LABELS_AND_RANGES,
            "Whether units, axes, categories, legend and data providers match the intended data.",
        ),
        ReviewItem(
            ReviewTopic.SOURCE_ASSURANCE,
            "Native Chart PDF export is unsupported; review it in its embedding application.",
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


ADAPTER = ChartAdapter()
