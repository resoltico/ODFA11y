# SPDX-License-Identifier: MPL-2.0
"""Expose authored visibility declarations without evaluating conditions or cached state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import reading_context_path
from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import FactKeys, Location, rules

from .reading_order import audit_reading_order
from .revisions import audit_revisions

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

FIELDS = {qn("text", name) for name in ("hidden-text", "conditional-text", "hidden-paragraph")}
BOOLEAN = {None, "true", "false", "1", "0"}


def audit_visibility(document: OdfDocument, report: Report) -> None:
    """Inspect relationships and retain visibility uncertainty for human/native review."""
    tree = document.tree(Part.CONTENT)
    audit_revisions(tree, report)
    rows: list[dict[str, object]] = []
    for node in select_elements(tree, "//office:body//*"):
        section = node.tag == qn("text", "section")
        conditional = node.get(qn("text", "condition"))
        display = node.get(qn("text", "display"))
        if node.tag not in FIELDS and not (
            section and (conditional is not None or display in {"none", "condition"})
        ):
            continue
        location = Location.indexed(reading_context_path(node), "visibility", len(rows) + 1)
        rows.append({
            "target": location.path,
            "kind": str(node.tag).split("}")[-1],
            "condition": conditional,
            "display": display,
            "cached_hidden": node.get(qn("text", "is-hidden")),
            "cached_condition": node.get(qn("text", "current-value")),
        })
        if not _coherent(node):
            report.add(
                rules.HIDDEN002,
                location=location,
                details={
                    "native_editing": (
                        "Resolve visibility declarations in Writer; no condition is evaluated."
                    )
                },
            )
    if rows:
        report.add(rules.HIDDEN001, details={"contexts": len(rows)})
    report.facts[FactKeys.TEXT_VISIBILITY_CONTEXTS] = rows
    audit_reading_order(document, report)


def _coherent(node: etree._Element) -> bool:
    condition = node.get(qn("text", "condition"))
    if node.tag == qn("text", "section"):
        display = node.get(qn("text", "display"))
        return (display == "none" and condition is None) or (
            display == "condition" and bool(condition and condition.strip())
        )
    if not condition or not condition.strip():
        return False
    if any(node.get(qn("text", name)) not in BOOLEAN for name in ("is-hidden", "current-value")):
        return False
    required = (
        ("string-value-if-true", "string-value-if-false")
        if node.tag == qn("text", "conditional-text")
        else ("string-value",)
        if node.tag == qn("text", "hidden-text")
        else ()
    )
    return all(qn("text", name) in node.attrib for name in required)
