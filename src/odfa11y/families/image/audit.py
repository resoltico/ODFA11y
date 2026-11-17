# SPDX-License-Identifier: AGPL-3.0-only
"""Audit the standard image body without fetching or converting its graphic."""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from odfa11y.concepts import GraphicIdentity, audit_graphic_role
from odfa11y.concepts.domains import GRAPHICS
from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.families.image.payload import inspect_payload
from odfa11y.odf import NS, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.odf.resources import local_resource_path
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class ImageMeasurements:
    """Measurements produced by image analysis; None denotes unmeasured data."""

    producer: Literal["image"] = field(default="image", init=False)
    graphic_count: Annotated[int | None, Description("Graphic frames in an Image document.")] = None


def audit_image(document: OdfDocument, report: Report, metadata: DocumentMetadata) -> None:
    """Check the mandatory frame, description and local/embedded resource boundary."""
    frames = [node for _, node in GRAPHICS.enumerate(document)]
    report.measure(ImageMeasurements(graphic_count=len(frames)))
    if len(frames) != 1:
        report.raise_(rules.IMAGE003, location=Location(f"{Part.CONTENT}/image"))
        return
    frame = frames[0]
    report.observe_review(Topic.IMAGE_MEANING, Topic.SOURCE_BOUNDARY)
    name = frame.get(xml_names.DRAW_NAME)
    location = (
        Location.named(Part.CONTENT, "frame", name)
        if name
        else Location.indexed(Part.CONTENT, "frame", 1)
    )
    images = select_elements(frame, "./draw:image")
    if not images:
        report.raise_(rules.IMAGE004, "Image frame has no image payload.", location=location)
    description = (frame.findtext("svg:title", namespaces=NS) or "") + (
        frame.findtext("svg:desc", namespaces=NS) or ""
    )
    href = images[0].get(xml_names.XLINK_HREF) if images else None
    identity = GraphicIdentity(document, frames)
    decorative = audit_graphic_role(document, frame, report)
    if not description.strip() and not decorative:
        report.raise_(
            rules.GRAPHIC001,
            location=Location(identity.target(frame)),
            details={"frame": name},
            decision=identity.open_decision(frame, GRAPHIC_ALTERNATIVE),
        )
    for image in images:
        problem, review = inspect_payload(document, image)
        if problem:
            report.raise_(rules.IMAGE002, problem, location=location)
        if review:
            report.raise_(rules.IMAGE001, location=location)
        href = image.get(xml_names.XLINK_HREF)
        embedded = image.find("office:binary-data", NS)
        local = local_resource_path(href) if href else None
        if embedded is None and (local is None or not document.storage.has(local)):
            report.raise_(
                rules.IMAGE005,
                "Image resource is external, unavailable or not embedded; it was not fetched.",
                location=location,
            )
