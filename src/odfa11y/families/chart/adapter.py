# SPDX-License-Identifier: MPL-2.0
"""Chart source assurance, using standard document metadata for its alternative."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.content import protected_xml
from odfa11y.odf import Family, Part, select_elements

from .audit import audit_chart

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Finding


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    return tuple(protected_xml(body) for body in bodies)


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed: int) -> bool:
    return removed == 0 and before == after


def _language(document: OdfDocument) -> str | None:
    del document
    return None


def _set_language(document: OdfDocument, tag: str) -> bool:
    del document, tag
    return False


def _template(findings: Mapping[str, Sequence[Finding]]) -> list[str]:
    del findings
    return []  # Chart's title/alternative use the common [document] template.


ADAPTER = FamilyAdapter(
    name="chart",
    family=Family.CHART,
    audit=audit_chart,
    default_language=_language,
    set_default_language=_set_language,
    snapshot=_snapshot,
    preserved=_preserved,
    config_tables={},
    template=_template,
    review_items=(
        ReviewItem(
            "chart meaning",
            "Whether the document description conveys the chart's trends, values and conclusion.",
        ),
        ReviewItem(
            "labels and ranges",
            "Whether units, axes, categories, legend and data providers match the intended data.",
        ),
        ReviewItem(
            "source assurance",
            "Native Chart PDF export is unsupported; review it in its embedding application.",
        ),
    ),
)
