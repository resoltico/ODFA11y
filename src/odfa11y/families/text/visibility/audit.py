# SPDX-License-Identifier: MPL-2.0
"""Expose authored visibility declarations without evaluating conditions or cached state."""

from typing import Annotated, Literal
lazy from dataclasses import dataclass, field

from lxml import etree

from odfa11y.concepts import reading_context_path
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.families.text.visibility.reading_order import audit_reading_order
from odfa11y.families.text.visibility.revisions import audit_revisions
from odfa11y.odf import Part, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import TargetPath
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

FIELDS = {qn("text", name) for name in ("hidden-text", "conditional-text", "hidden-paragraph")}
BOOLEAN = {None, "true", "false", "1", "0"}


@dataclass(frozen=True, slots=True)
class VisibilityContext:
    target: TargetPath
    kind: str
    condition: str | None
    display: str | None
    cached_hidden: str | None
    cached_condition: str | None


@dataclass(frozen=True, slots=True)
class VisibilityMeasurements:
    """Measurements produced by text-visibility analysis; None denotes unmeasured data."""

    producer: Literal["text-visibility"] = field(default="text-visibility", init=False)
    visibility_contexts: Annotated[
        list[VisibilityContext] | None,
        Description("Visibility conditions and cached states, without evaluation."),
    ] = None


def audit_visibility(document: OdfDocument, report: Report) -> None:
    """Inspect relationships and retain visibility uncertainty for human/native review."""
    tree = document.tree(Part.CONTENT)
    audit_revisions(tree, report)
    rows: list[VisibilityContext] = []
    for node in select_elements(tree, "//office:body//*"):
        section = node.tag == xml_names.TEXT_SECTION
        conditional = node.get(xml_names.TEXT_CONDITION)
        display = node.get(xml_names.TEXT_DISPLAY)
        if node.tag not in FIELDS and not (
            section and (conditional is not None or display in {"none", "condition"})
        ):
            continue
        location = Location.indexed(reading_context_path(node), "visibility", len(rows) + 1)
        rows.append(
            VisibilityContext(
                location.path,
                str(node.tag).split("}")[-1],
                conditional,
                display,
                node.get(xml_names.TEXT_IS_HIDDEN),
                node.get(xml_names.TEXT_CURRENT_VALUE),
            )
        )
        if not _coherent(node):
            report.raise_(
                rules.ORDER001,
                location=location,
                details={
                    "native_editing": (
                        "Resolve visibility declarations in Writer; no condition is evaluated."
                    )
                },
            )
    if rows:
        report.observe_review(Topic.HIDDEN_CONTENT)
        report.raise_(rules.ORDER003, details={"contexts": len(rows)})
    report.measure(VisibilityMeasurements(visibility_contexts=rows))
    audit_reading_order(document, report)


def _coherent(node: etree._Element) -> bool:
    condition = node.get(xml_names.TEXT_CONDITION)
    if node.tag == xml_names.TEXT_SECTION:
        display = node.get(xml_names.TEXT_DISPLAY)
        return (display == "none" and condition is None) or (
            display == "condition" and bool(condition and condition.strip())
        )
    if not condition or not condition.strip():
        return False
    if any(node.get(qn("text", name)) not in BOOLEAN for name in ("is-hidden", "current-value")):
        return False
    required = (
        ("string-value-if-true", "string-value-if-false")
        if node.tag == xml_names.TEXT_CONDITIONAL_TEXT
        else ("string-value",)
        if node.tag == xml_names.TEXT_HIDDEN_TEXT
        else ()
    )
    return all(qn("text", name) in node.attrib for name in required)
