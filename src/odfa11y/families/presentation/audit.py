# SPDX-License-Identifier: MPL-2.0
"""Audit presentation pages, content, descriptions and explicit navigation."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from odfa11y.content import (
    SHAPE_TAGS,
    GraphicIdentity,
    navigation_problem,
    page_fingerprint,
    page_shapes,
    pages,
    visible_words,
)
from odfa11y.odf import NS, Part, qn, select_elements
from odfa11y.report import Location, rules

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def audit_document(document: OdfDocument, report: Report) -> None:
    """Report semantic defects without executing scripts, links or rendering."""
    available = pages(document)
    names = Counter(page.get(qn("draw", "name")) for page in available)
    identities = Counter(
        identity
        for node in document.tree(Part.CONTENT).iter()
        if (identity := node.get(XML_ID) or node.get(qn("draw", "id")))
    )
    report.metadata["page_count"] = len(available)
    if not available:
        report.add(rules.PRES001, location=Location(Part.CONTENT))
    for index, page in enumerate(available, 1):
        name = page.get(qn("draw", "name"))
        location = (
            Location.named(Part.CONTENT, "page", name)
            if name
            else Location.indexed(Part.CONTENT, "page", index)
        )
        details = {"page": name, "fingerprint": page_fingerprint(page)}
        if not name or names[name] != 1:
            report.add(rules.PRES001, location=location)
        if not (page.findtext("svg:title", namespaces=NS) or "").strip():
            report.add(rules.PRES002, location=location, details=details)
        order = page.get(qn("draw", "nav-order"))
        shapes = page_shapes(page)
        details["shape_identities"] = [
            shape.get(XML_ID) or shape.get(qn("draw", "id")) for shape in shapes
        ]
        if order is not None:
            problem = navigation_problem(page, tuple(order.split()), identities)
            if problem:
                report.add(rules.PRES005, problem, location=location, details=details)
        elif len(shapes) > 1:
            report.add(rules.PRES006, location=location, details=details)
    _graphics(document, report)
    _links(document, report)
    _review_content(document, report)


def _graphics(document: OdfDocument, report: Report) -> None:
    shapes = [
        node
        for node in select_elements(document.tree(Part.CONTENT), "//office:body//*")
        if node.tag in SHAPE_TAGS
    ]
    identity = GraphicIdentity(document, shapes)
    report.metadata["shape_count"] = len(shapes)
    for index, shape in enumerate(shapes, 1):
        name = shape.get(qn("draw", "name"))
        description = (shape.findtext("svg:title", namespaces=NS) or "") + (
            shape.findtext("svg:desc", namespaces=NS) or ""
        )
        if description.strip():
            continue
        if shape.tag == qn("draw", "page-thumbnail") or (
            shape.get(qn("presentation", "placeholder")) == "true" and not visible_words(shape)
        ):
            continue
        payload = select_elements(shape, "./draw:image | ./draw:object | ./draw:object-ole")
        if not payload and visible_words(shape):
            continue
        image = shape.find("draw:image", NS)
        selector = name or (image.get(qn("xlink", "href")) if image is not None else None)
        addressed = identity.matching(selector) if selector else [shape]
        rule = rules.PRES003 if payload else rules.PRES004
        report.add(
            rule,
            location=Location.named(Part.CONTENT, "shape", name)
            if name
            else Location.indexed(Part.CONTENT, "shape", index),
            details={
                "shape": name,
                "selector": selector,
                "fingerprint": identity.fingerprint(addressed),
            },
        )


def _links(document: OdfDocument, report: Report) -> None:
    links = select_elements(
        document.tree(Part.CONTENT), "//office:body//text:a | //office:body//draw:a"
    )
    report.metadata["link_count"] = len(links)
    for index, link in enumerate(links, 1):
        metadata = select_elements(link, ".//svg:title | .//svg:desc")
        if not (
            visible_words(link)
            or (link.get(qn("office", "name")) or "").strip()
            or any((node.text or "").strip() for node in metadata)
        ):
            report.add(rules.PRES009, location=Location.indexed(Part.CONTENT, "link", index))


def _review_content(document: OdfDocument, report: Report) -> None:
    notes = select_elements(
        document.tree(Part.CONTENT),
        "//office:body//presentation:notes | //office:body//office:annotation",
    )
    if any(visible_words(note) for note in notes):
        report.add(
            rules.PRES008,
            details={"content_count": sum(bool(visible_words(note)) for note in notes)},
        )
    hidden_styles = {
        node.get(qn("style", "name"))
        for part in (Part.CONTENT, Part.STYLES)
        for node in select_elements(
            document.tree(part),
            "//style:style[style:drawing-page-properties[@presentation:visibility='hidden']]",
        )
    }
    hidden = [
        page for page in pages(document) if page.get(qn("draw", "style-name")) in hidden_styles
    ]
    if hidden:
        report.add(rules.PRES007, details={"hidden_pages": len(hidden)})
