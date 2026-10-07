# SPDX-License-Identifier: MPL-2.0
"""Audit native MathML structure and supplied spoken alternatives."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import Part, qn
from odfa11y.report import Location, rules

from .expression import expression, fingerprint

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

TOKENS = {qn("math", name) for name in ("mi", "mn", "mo", "mtext", "ms", "ci", "cn", "csymbol")}
CONTENT_VALUES = {
    qn("math", name)
    for name in (
        "integers",
        "reals",
        "rationals",
        "naturalnumbers",
        "complexes",
        "primes",
        "emptyset",
        "exponentiale",
        "imaginaryi",
        "notanumber",
        "true",
        "false",
        "pi",
        "eulergamma",
        "infinity",
        "set",
        "list",
        "vector",
        "matrix",
    )
}
NONEXPRESSION = {qn("math", name) for name in ("annotation", "annotation-xml", "mphantom")}


def _meaningful(node: etree._Element) -> bool:
    if node.tag in NONEXPRESSION or any(
        parent.tag in NONEXPRESSION for parent in node.iterancestors()
    ):
        return False
    if node.tag in CONTENT_VALUES:
        return True
    if node.tag == qn("math", "ms") and (node.get("lquote", '"') or node.get("rquote", '"')):
        return True
    if node.tag == qn("math", "csymbol") and (node.get("definitionURL") or "").strip():
        return True
    if node.tag == qn("math", "mglyph"):
        return bool((node.get("src") or "").strip())
    return node.tag in TOKENS and bool("".join(node.itertext()).strip())


def audit_formula(document: OdfDocument, report: Report) -> None:
    """Check formula applicability and semantics; formal MathML validation is a schema gate."""
    root = expression(document)
    location = Location(f"{Part.CONTENT}/formula")
    if root is None:
        report.add(
            rules.MATH001,
            "Formula content must be a native MathML root; flat office wrappers are unsupported.",
            location=location,
        )
        return
    nodes = [node for node in root.iter() if isinstance(node.tag, str)]
    report.metadata["mathml_element_count"] = len(nodes)
    if not any(_meaningful(node) for node in nodes):
        report.add(rules.MATH001, "The mathematical expression is empty.", location=location)
    if not (root.get("alttext") or "").strip():
        report.add(rules.MATH002, location=location, details={"fingerprint": fingerprint(root)})
    if any(
        node.get("href") or node.get("src") or node.get("altimg") or node.get(qn("xlink", "href"))
        for node in nodes
    ):
        report.add(rules.MATH003, location=location)
