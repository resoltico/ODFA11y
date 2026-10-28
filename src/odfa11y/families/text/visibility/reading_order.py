# SPDX-License-Identifier: MPL-2.0
"""Identify authored layout conditions whose reading order needs native human review."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from odfa11y.families.text.contexts import text_nodes
from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import FactKeys, Location, rules

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_reading_order(document: OdfDocument, report: Report) -> None:
    """Report declared layout uncertainty; notes retain their owning NOTE001 review."""
    counts: Counter[str] = Counter()
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        for columns in select_elements(tree, "//style:columns"):
            if _multiple(columns):
                counts["multi-column"] += 1
    content = document.tree(Part.CONTENT)
    counts["floating-frame"] = sum(
        node.get(qn("text", "anchor-type")) != "as-char"
        for node in text_nodes(content, qn("draw", "frame"))
    )
    counts["section"] = len(text_nodes(content, qn("text", "section")))
    counts["note"] = len(text_nodes(content, qn("text", "note")))
    for kind in ("multi-column", "floating-frame", "section"):
        if counts[kind]:
            report.add(
                rules.ORDER001,
                location=Location(Part.CONTENT.value),
                details={
                    "kind": kind,
                    "count": counts[kind],
                    "scope": "Declared layout; native use and reading order require review.",
                },
            )
    report.facts[FactKeys.TEXT_READING_ORDER_COUNTS] = dict(counts)


def _multiple(columns: etree._Element) -> bool:
    declared = columns.get(qn("fo", "column-count"))
    try:
        return (declared is not None and int(declared) > 1) or len(
            columns.findall(qn("style", "column"))
        ) > 1
    except ValueError:
        return True  # Unresolved layout count still requires native reading-order review.
