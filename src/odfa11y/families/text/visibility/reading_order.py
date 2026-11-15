# SPDX-License-Identifier: MPL-2.0
"""Identify authored layout conditions whose reading order needs native human review."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Literal

lazy from lxml import etree

from odfa11y.contracts import Description
from odfa11y.families.text.contexts import text_nodes
from odfa11y.odf import Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class ReadingOrderMeasurements:
    """Measurements produced by text-reading-order analysis; None denotes unmeasured data."""

    producer: Literal["text-reading-order"] = field(default="text-reading-order", init=False)
    reading_order_counts: Annotated[
        dict[str, int] | None,
        Description("Declared layout conditions needing native reading-order review."),
    ] = None


def audit_reading_order(document: OdfDocument, report: Report) -> None:
    """Report declared layout uncertainty; notes retain their owning NOTE001 review."""
    counts: Counter[str] = Counter()
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        for columns in select_elements(tree, "//style:columns"):
            if _multiple(columns):
                counts["multi-column"] += 1
    content = document.tree(Part.CONTENT)
    counts["floating-frame"] = sum(
        node.get(xml_names.TEXT_ANCHOR_TYPE) != "as-char"
        for node in text_nodes(content, xml_names.DRAW_FRAME)
    )
    counts["section"] = len(text_nodes(content, xml_names.TEXT_SECTION))
    counts["note"] = len(text_nodes(content, xml_names.TEXT_NOTE))
    for kind in ("multi-column", "floating-frame", "section"):
        if counts[kind]:
            report.raise_(
                rules.ORDER002,
                location=Location(Part.CONTENT.value),
                details={
                    "kind": kind,
                    "count": counts[kind],
                    "scope": "Declared layout; native use and reading order require review.",
                },
            )
    report.measure(ReadingOrderMeasurements(reading_order_counts=dict(counts)))


def _multiple(columns: etree._Element) -> bool:
    declared = columns.get(xml_names.FO_COLUMN_COUNT)
    try:
        return (declared is not None and int(declared) > 1) or len(
            columns.findall(xml_names.STYLE_COLUMN)
        ) > 1
    except ValueError:
        return True  # Unresolved layout count still requires native reading-order review.
