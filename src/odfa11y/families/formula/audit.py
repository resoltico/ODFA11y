# SPDX-License-Identifier: MPL-2.0
"""Audit native MathML structure and supplied spoken alternatives."""

from typing import Annotated, Literal
lazy from dataclasses import dataclass, field

from lxml import etree

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.families.formula.domain import FORMULA
from odfa11y.families.formula.kinds import FORMULA_ALTERNATIVE
from odfa11y.odf import Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

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


@dataclass(frozen=True, slots=True)
class FormulaMeasurements:
    """Measurements produced by formula analysis; None denotes unmeasured data."""

    producer: Literal["formula"] = field(default="formula", init=False)
    element_count: Annotated[int | None, Description("Inspected MathML elements.")] = None


def _meaningful(node: etree._Element) -> bool:
    if node.tag in NONEXPRESSION or any(
        parent.tag in NONEXPRESSION for parent in node.iterancestors()
    ):
        return False
    if node.tag in CONTENT_VALUES:
        return True
    if node.tag == xml_names.MATH_MS and (node.get("lquote", '"') or node.get("rquote", '"')):
        return True
    if node.tag == xml_names.MATH_CSYMBOL and (node.get("definitionURL") or "").strip():
        return True
    if node.tag == xml_names.MATH_MGLYPH:
        return bool((node.get("src") or "").strip())
    return node.tag in TOKENS and bool("".join(node.itertext()).strip())


def audit_formula(document: OdfDocument, report: Report, metadata: DocumentMetadata) -> None:
    """Check formula applicability and semantics; formal MathML validation is a schema gate."""
    entries = tuple(FORMULA.enumerate(document))
    root = entries[0][1] if entries else None
    location = Location(f"{Part.CONTENT}/formula")
    if root is None:
        report.raise_(
            rules.MATH001,
            "Formula content must be a native MathML root; flat office wrappers are unsupported.",
            location=location,
        )
        return
    nodes = [node for node in root.iter() if isinstance(node.tag, str)]
    report.measure(FormulaMeasurements(element_count=len(nodes)))
    if not any(_meaningful(node) for node in nodes):
        report.raise_(rules.MATH002, "The mathematical expression is empty.", location=location)
    if not (root.get("alttext") or "").strip():
        report.raise_(
            rules.MATH003,
            location=location,
            decision=OpenDecision(
                FORMULA_ALTERNATIVE,
                FORMULA.binding(document, entries[0][0]),
                {"alternative": root.get("alttext")},
            ),
        )
    if any(
        node.get("href") or node.get("src") or node.get("altimg") or node.get(xml_names.XLINK_HREF)
        for node in nodes
    ):
        report.raise_(rules.MATH004, location=location)
