# SPDX-License-Identifier: AGPL-3.0-only
"""Audit headings, graphics and tables for accessible structure."""

import re
from typing import Annotated, Literal
lazy from dataclasses import dataclass, field

from odfa11y.concepts import (
    GraphicIdentity,
    audit_graphic_role,
    visible_words,
)
from odfa11y.concepts.domains import GRAPHICS
from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.families.text.answers import MAX_HEADING_LEVEL
from odfa11y.families.text.domains import HEADINGS
from odfa11y.families.text.headings.edit import (
    heading_fingerprint,
)
from odfa11y.families.text.kinds import HEADING_LEVEL
from odfa11y.odf import NS, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target, require_target
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

MANUAL_NUMBER_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)(?P<punct>[.)])?\s+")


MAX_SIMPLE_HEADING_NUMBER = 99


@dataclass(frozen=True, slots=True)
class TextContentMeasurements:
    """Measurements produced by text-content analysis; None denotes unmeasured data."""

    producer: Literal["text-content"] = field(default="text-content", init=False)
    heading_count: Annotated[
        int | None, Description("Structural headings in current reading contexts.")
    ] = None
    graphic_count: Annotated[
        int | None, Description("Graphic objects in current reading contexts.")
    ] = None


def audit_headings(document: OdfDocument, report: Report) -> None:
    """Report heading structure over the canonical heading domain."""
    entries = tuple(HEADINGS.enumerate(document))
    headings = [node for _, node in entries]
    if headings:
        report.observe_review(Topic.HEADINGS)
    report.measure(TextContentMeasurements(heading_count=len(headings)))
    previous_level: int | None = None
    for path, heading in entries:
        raw = heading.get(xml_names.TEXT_OUTLINE_LEVEL)
        text = visible_words(heading)
        try:
            level = int(raw) if raw is not None else 0
        except ValueError:
            level = 0
        location = Location(path)
        excerpt = {"text": text}
        decision = OpenDecision(
            HEADING_LEVEL,
            Target((location).path, Fingerprint(heading_fingerprint(heading, document))),
            {"level": raw},
        )
        if not 1 <= level <= MAX_HEADING_LEVEL:
            report.raise_(
                rules.HEADING001,
                "Heading has no valid text:outline-level.",
                location=location,
                details=excerpt,
                decision=OpenDecision(
                    HEADING_LEVEL,
                    Target(
                        (location).path,
                        Fingerprint(require_target(decision.target).fingerprint),
                    ),
                    decision.current,
                ),
            )
            continue
        if previous_level is None and level > 1:
            report.raise_(
                rules.HEADING002,
                f"Heading hierarchy starts at level {level}; expected level 1.",
                location=location,
                details=excerpt,
                decision=decision,
            )
        elif previous_level is not None and level > previous_level + 1:
            report.raise_(
                rules.HEADING003,
                f"Heading hierarchy skips from level {previous_level} to {level}.",
                location=location,
                details=excerpt,
                decision=decision,
            )
        previous_level = level
        if _looks_manually_numbered_heading(text):
            report.raise_(
                rules.HEADING004,
                (
                    "Heading appears to use manually typed numbering; integrated "
                    "numbering is safer for accessible export."
                ),
                location=location,
                details={"text": text},
            )
    if not headings:
        report.raise_(
            rules.HEADING005,
            "No structural headings were found. This may be legitimate for a very short document.",
            location=Location(Part.CONTENT.value),
        )


def audit_images(document: OdfDocument, report: Report) -> None:
    """Report graphics and embedded objects that lack alternative text."""
    frames = [node for _, node in GRAPHICS.enumerate(document)]
    if frames:
        report.observe_review(Topic.ALT_TEXT, Topic.COLOUR, Topic.READING_ORDER, Topic.LAYOUT)
    for group in select_elements(document.tree(Part.CONTENT), "//office:body//draw:g"):
        audit_graphic_role(document, group, report)
    identity = GraphicIdentity(document, frames)
    report.measure(TextContentMeasurements(graphic_count=len(frames)))
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
            report.raise_(
                rules.GRAPHIC001,
                "Graphic object has neither accessible title nor description.",
                location=Location(identity.target(frame)),
                details={
                    "frame": declared_name,
                    "href": href,
                },
                decision=identity.open_decision(frame, GRAPHIC_ALTERNATIVE),
            )


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
