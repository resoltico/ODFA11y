# SPDX-License-Identifier: MPL-2.0
"""Audit headings, graphics and tables for accessible structure."""

import re

lazy from lxml import etree

from odfa11y.concepts import (
    SHAPE_TAGS,
    GraphicIdentity,
    audit_graphic_role,
    eligible_text_node,
    visible_words,
)
from odfa11y.decisions import OpenDecision
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.headings.edit import (
    MAX_HEADING_LEVEL,
    heading_fingerprint,
    heading_location,
)
from odfa11y.families.text.kinds import HEADING_LEVEL
from odfa11y.odf import NS, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import FactKeys, Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target, require_target
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

MANUAL_NUMBER_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)(?P<punct>[.)])?\s+")


MAX_SIMPLE_HEADING_NUMBER = 99


def audit_headings(
    tree: etree._ElementTree, report: Report, document: OdfDocument | None = None
) -> None:
    """Report heading-structure defects such as skipped levels and empty headings."""
    headings = text_nodes(tree, xml_names.TEXT_H, main_only=True)
    report.facts[FactKeys.TEXT_HEADING_COUNT] = len(headings)
    previous_level: int | None = None
    for index, heading in enumerate(headings, start=1):
        raw = heading.get(xml_names.TEXT_OUTLINE_LEVEL)
        text = visible_words(heading)
        try:
            level = int(raw) if raw is not None else 0
        except ValueError:
            level = 0
        location = heading_location(heading, index)
        excerpt = {"text": text[:80]}
        decision = OpenDecision(
            HEADING_LEVEL,
            Target((location).path, Fingerprint(heading_fingerprint(heading, document))),
            {"level": raw},
            (rules.HEADING002.id,),
        )
        if not 1 <= level <= MAX_HEADING_LEVEL:
            report.add(
                rules.HEADING001,
                "Heading has no valid text:outline-level.",
                location=location,
                details=excerpt,
            )
            report.add_decision(
                OpenDecision(
                    HEADING_LEVEL,
                    Target(
                        (location).path,
                        Fingerprint(require_target(decision.target).fingerprint),
                    ),
                    decision.current,
                    (rules.HEADING001.id,),
                )
            )
            continue
        if previous_level is None and level > 1:
            report.add(
                rules.HEADING002,
                f"Heading hierarchy starts at level {level}; expected level 1.",
                location=location,
                details=excerpt,
            )
        elif previous_level is not None and level > previous_level + 1:
            report.add(
                rules.HEADING002,
                f"Heading hierarchy skips from level {previous_level} to {level}.",
                location=location,
                details=excerpt,
            )
        if (previous_level is None and level > 1) or (
            previous_level is not None and level > previous_level + 1
        ):
            report.add_decision(decision)
        previous_level = level
        if _looks_manually_numbered_heading(text):
            report.add(
                rules.HEADING003,
                (
                    "Heading appears to use manually typed numbering; integrated "
                    "numbering is safer for accessible export."
                ),
                location=location,
                details={"text": text},
            )
    if not headings:
        report.add(
            rules.HEADING004,
            "No structural headings were found. This may be legitimate for a very short document.",
            location=Location(Part.CONTENT.value),
        )


def audit_images(document: OdfDocument, report: Report) -> None:
    """Report graphics and embedded objects that lack alternative text."""
    tree = document.tree(Part.CONTENT)
    frames = [
        node
        for node in select_elements(tree, "//office:body//*")
        if node.tag in SHAPE_TAGS and node.tag != xml_names.DRAW_G and eligible_text_node(node)
    ]
    for group in select_elements(document.tree(Part.CONTENT), "//office:body//draw:g"):
        audit_graphic_role(document, group, report)
    identity = GraphicIdentity(document, frames)
    report.facts[FactKeys.TEXT_GRAPHIC_COUNT] = len(frames)
    for frame in frames:
        if audit_graphic_role(document, frame, report):
            continue
        if visible_words(frame) and not select_elements(
            frame, "./draw:image | ./draw:object | ./draw:object-ole"
        ):
            continue
        title = frame.findtext("svg:title", namespaces=NS)
        desc = frame.findtext("svg:desc", namespaces=NS)
        declared_name = frame.get(xml_names.DRAW_NAME)
        image = frame.find("draw:image", NS)
        href = image.get(xml_names.XLINK_HREF) if image is not None else None
        if not ((title and title.strip()) or (desc and desc.strip())):
            report.add(
                rules.GRAPHIC003,
                "Graphic object has neither accessible title nor description.",
                location=Location(identity.target(frame)),
                details={
                    "frame": declared_name,
                    "href": href,
                },
            )

            report.add_decision(identity.open_decision(frame, rules.GRAPHIC003.id))


def _looks_manually_numbered_heading(text: str) -> bool:
    match = MANUAL_NUMBER_RE.match(text)
    if not match:
        return False
    number = match.group("num")
    punct = match.group("punct")
    if "." in number or punct:
        return True
    try:
        return int(number) <= MAX_SIMPLE_HEADING_NUMBER
    except ValueError:
        return False
