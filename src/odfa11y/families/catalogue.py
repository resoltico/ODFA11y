# SPDX-License-Identifier: MPL-2.0
"""Which adapter serves which kind of document."""

from odfa11y.families.chart import ADAPTER as CHART_ADAPTER
from odfa11y.families.database import ADAPTER as DATABASE_ADAPTER
from odfa11y.families.formula import ADAPTER as FORMULA_ADAPTER
from odfa11y.families.generic import GENERIC
from odfa11y.families.image import ADAPTER as IMAGE_ADAPTER
from odfa11y.families.pages import DRAWING_ADAPTER, PRESENTATION_ADAPTER
from odfa11y.families.spreadsheet import ADAPTER as SPREADSHEET_ADAPTER
from odfa11y.families.text import ADAPTER as TEXT_ADAPTER
from odfa11y.odf import Family
lazy from odfa11y.families.spec import FamilyAdapter
lazy from odfa11y.odf import DocumentKind

REGISTRY: dict[Family, FamilyAdapter] = {
    Family.TEXT: TEXT_ADAPTER,
    Family.DATABASE: DATABASE_ADAPTER,
    Family.IMAGE: IMAGE_ADAPTER,
    Family.CHART: CHART_ADAPTER,
    Family.FORMULA: FORMULA_ADAPTER,
    Family.PRESENTATION: PRESENTATION_ADAPTER,
    Family.DRAWING: DRAWING_ADAPTER,
    Family.SPREADSHEET: SPREADSHEET_ADAPTER,
}


def adapter_for(kind: DocumentKind | None) -> FamilyAdapter:
    """Select the adapter for a document kind; kinds without one get the generic adapter.

    Returns
    -------
    FamilyAdapter
        The family's adapter, or the generic adapter.

    """
    return REGISTRY.get(kind.family, GENERIC) if kind is not None else GENERIC
