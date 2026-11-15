# SPDX-License-Identifier: MPL-2.0
"""Which adapter serves which kind of document."""

from odfa11y.errors import DocumentRefusal, Remedy, RemedyAction
from odfa11y.families.chart import SPEC as CHART_SPEC
from odfa11y.families.database import SPEC as DATABASE_SPEC
from odfa11y.families.formula import SPEC as FORMULA_SPEC
from odfa11y.families.image import SPEC as IMAGE_SPEC
from odfa11y.families.pages import DRAWING_SPEC, PRESENTATION_SPEC
from odfa11y.families.spreadsheet import SPEC as SPREADSHEET_SPEC
from odfa11y.families.text import SPEC as TEXT_SPEC
from odfa11y.odf import Family
lazy from odfa11y.families.spec import FamilySpec
lazy from odfa11y.odf import DocumentKind

REGISTRY: dict[Family, FamilySpec] = {
    Family.TEXT: TEXT_SPEC,
    Family.DATABASE: DATABASE_SPEC,
    Family.IMAGE: IMAGE_SPEC,
    Family.CHART: CHART_SPEC,
    Family.FORMULA: FORMULA_SPEC,
    Family.PRESENTATION: PRESENTATION_SPEC,
    Family.DRAWING: DRAWING_SPEC,
    Family.SPREADSHEET: SPREADSHEET_SPEC,
}


def spec_for(kind: DocumentKind | None) -> FamilySpec | None:
    return REGISTRY.get(kind.family) if kind is not None else None


def require_spec(kind: DocumentKind | None) -> FamilySpec:
    spec = spec_for(kind)
    if spec is None:
        label = kind.name if kind is not None else "unrecognised source media type"
        message = (
            f"No supported source family for {label}; "
            "save a supported OpenDocument type in the source application."
        )
        raise DocumentRefusal(
            message,
            remedy=Remedy(
                RemedyAction.EDIT_IN_APPLICATION,
                label,
                "Save a supported OpenDocument type and regenerate the plan.",
            ),
        )
    return spec
