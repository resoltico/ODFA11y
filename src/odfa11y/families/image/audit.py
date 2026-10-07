# SPDX-License-Identifier: MPL-2.0
"""Audit the standard image body without fetching or converting its graphic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import GraphicIdentity, local_resource_path
from odfa11y.odf import NS, Part, qn, select_elements
from odfa11y.report import Location, rules

from .payload import inspect_payload

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_image(document: OdfDocument, report: Report) -> None:
    """Check the mandatory frame, description and local/embedded resource boundary."""
    frames = select_elements(document.tree(Part.CONTENT), "//office:body/office:image/draw:frame")
    report.metadata["image_frame_count"] = len(frames)
    if len(frames) != 1:
        report.add(rules.IMAGE001, location=Location(f"{Part.CONTENT}/image"))
        return
    frame = frames[0]
    name = frame.get(qn("draw", "name"))
    location = (
        Location.named(Part.CONTENT, "frame", name)
        if name
        else Location.indexed(Part.CONTENT, "frame", 1)
    )
    images = select_elements(frame, "./draw:image")
    if not images:
        report.add(rules.IMAGE001, "Image frame has no image payload.", location=location)
    description = (frame.findtext("svg:title", namespaces=NS) or "") + (
        frame.findtext("svg:desc", namespaces=NS) or ""
    )
    href = images[0].get(qn("xlink", "href")) if images else None
    selector = name or href
    identity = GraphicIdentity(document, frames)
    if not description.strip():
        report.add(
            rules.IMAGE002,
            location=location,
            details={
                "frame": name,
                "selector": selector,
                "fingerprint": identity.fingerprint(
                    identity.matching(selector) if selector else frames
                ),
            },
        )
    for image in images:
        problem, review = inspect_payload(document, image)
        if problem:
            report.add(rules.IMAGE004, problem, location=location)
        if review:
            report.add(rules.IMAGE005, location=location)
        href = image.get(qn("xlink", "href"))
        embedded = image.find("office:binary-data", NS)
        local = local_resource_path(href) if href else None
        if embedded is None and (local is None or not document.storage.has(local)):
            report.add(
                rules.IMAGE003,
                "Image resource is external, unavailable or not embedded; it was not fetched.",
                location=location,
            )
