# SPDX-License-Identifier: MPL-2.0
"""Chart source assurance, using standard document metadata for its alternative."""

from odfa11y.concepts import protected_xml
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.families.chart.audit import audit_chart
from odfa11y.families.spec import FamilySpec, ReviewItem, Unsupported
from odfa11y.odf import Family, Part, select_elements
lazy from odfa11y.odf import OdfDocument


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(protected_xml(body) for body in bodies)


def _preservation(document: OdfDocument) -> PreservationSnapshot:
    """Capture protected meaning.

    Returns
    -------
    PreservationSnapshot
        The family-owned protected facts.

    """
    return PreservationSnapshot(_snapshot(document))


SPEC = FamilySpec(
    family=Family.CHART,
    audit=audit_chart,
    kinds=(),
    export=Unsupported(
        "Native PDF export is unsupported for standalone chart documents; "
        "use the source application."
    ),
    snapshot=_preservation,
    language=None,
    review_items=(
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
    ),
)
