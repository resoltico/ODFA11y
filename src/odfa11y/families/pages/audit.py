# SPDX-License-Identifier: MPL-2.0
"""Audit presentation and drawing pages, content, descriptions and explicit navigation."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from odfa11y.content import (
    SHAPE_TAGS,
    GraphicIdentity,
    audit_graphic_role,
    document_links,
    link_decision,
    link_has_description,
    link_location,
    navigation_problem,
    page_fingerprint,
    page_location,
    page_shapes,
    pages,
    visible_words,
)
from odfa11y.decisions import OpenDecision
from odfa11y.decisions.kinds import PAGE_METADATA, PAGE_NAVIGATION
from odfa11y.odf import NS, Part, qn, select_elements
from odfa11y.report import FactKeys, Location

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

    from .profiles import PageProfile

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def audit_document(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    """Report semantic defects without executing scripts, links or rendering."""
    available = pages(document)
    names = Counter(page.get(qn("draw", "name")) for page in available)
    identities = Counter(
        identity
        for node in document.tree(Part.CONTENT).iter()
        if (identity := node.get(XML_ID) or node.get(qn("draw", "id")))
    )
    report.facts[FactKeys.PAGE_COUNT] = len(available)
    if not available:
        report.add(profile.rule(1), location=Location(Part.CONTENT))
    for index, page in enumerate(available, 1):
        _audit_page(document, page, index, names, identities, report=report, profile=profile)
    _graphics(document, report, profile)
    _links(document, report, profile)
    _review_content(document, report, profile)


def _audit_page(
    document: OdfDocument,
    page: etree._Element,
    index: int,
    names: Counter[str | None],
    identities: Counter[str],
    *,
    report: Report,
    profile: PageProfile,
) -> None:
    name = page.get(qn("draw", "name"))
    location = page_location(page, index)
    fingerprint = page_fingerprint(page, document)
    details = {"page": name}
    if not name or names[name] != 1:
        report.add(profile.rule(1), location=location)
    if not (page.findtext("svg:title", namespaces=NS) or "").strip():
        report.add(profile.rule(2), location=location, details=details)
        if not name or names[name] == 1:
            report.add_decision(
                OpenDecision(
                    PAGE_METADATA,
                    location,
                    fingerprint,
                    {
                        "title": page.findtext("svg:title", namespaces=NS),
                        "description": page.findtext("svg:desc", namespaces=NS),
                    },
                    (profile.rule(2).id,),
                )
            )
    order = page.get(qn("draw", "nav-order"))
    shapes = page_shapes(page)
    details["shape_identities"] = [
        shape.get(XML_ID) or shape.get(qn("draw", "id")) for shape in shapes
    ]
    if order is not None:
        problem = navigation_problem(page, tuple(order.split()), identities)
        if problem:
            report.add(profile.rule(5), problem, location=location, details=details)
    elif len(shapes) > 1:
        report.add(profile.rule(6), location=location, details=details)
    if (order is not None and navigation_problem(page, tuple(order.split()), identities)) or (
        order is None and len(shapes) > 1
    ):
        supplied_ids = details["shape_identities"]
        if (not name or names[name] == 1) and all(
            identity and identities[identity] == 1 for identity in supplied_ids
        ):
            report.add_decision(
                OpenDecision(
                    PAGE_NAVIGATION,
                    location,
                    fingerprint,
                    {
                        "navigation": tuple(order.split()) if order else None,
                        "available_identities": supplied_ids,
                    },
                    ((profile.rule(5).id if order is not None else profile.rule(6).id),),
                )
            )


def _graphics(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    shapes = [
        node
        for node in select_elements(document.tree(Part.CONTENT), "//office:body//*")
        if node.tag in SHAPE_TAGS
    ]
    identity = GraphicIdentity(document, shapes)
    report.facts[FactKeys.PAGE_SHAPE_COUNT] = len(shapes)
    for shape in shapes:
        decorative = audit_graphic_role(document, shape, report)
        if decorative or shape.tag == qn("draw", "g"):
            continue
        name = shape.get(qn("draw", "name"))
        description = (shape.findtext("svg:title", namespaces=NS) or "") + (
            shape.findtext("svg:desc", namespaces=NS) or ""
        )
        if description.strip():
            continue
        if _skipped_shape(shape, profile):
            continue
        payload = select_elements(shape, "./draw:image | ./draw:object | ./draw:object-ole")
        if not payload and visible_words(shape):
            continue
        rule = profile.rule(3) if payload else profile.rule(4)
        report.add(
            rule,
            location=Location(identity.target(shape)),
            details={
                "shape": name,
            },
        )

        report.add_decision(identity.open_decision(shape, rule.id))


def _links(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    links = document_links(document)
    report.facts[FactKeys.PAGE_LINK_COUNT] = len(links)
    for index, link in enumerate(links, 1):
        if not link_has_description(link):
            report.add(
                profile.rule(9),
                location=link_location(link, index),
            )
            report.add_decision(link_decision(document, link, index, profile.rule(9).id))


def _review_content(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    notes = select_elements(
        document.tree(Part.CONTENT),
        "//office:body//presentation:notes | //office:body//office:annotation",
    )
    if any(visible_words(note) for note in notes):
        report.add(
            profile.rule(8),
            details={"content_count": sum(bool(visible_words(note)) for note in notes)},
        )
    hidden = profile.hidden_content(document)
    if hidden:
        report.add(profile.rule(7), details=hidden)


def _skipped_shape(shape: etree._Element, profile: PageProfile) -> bool:
    return profile.skip_presentation_shapes and (
        shape.tag == qn("draw", "page-thumbnail")
        or (shape.get(qn("presentation", "placeholder")) == "true" and not visible_words(shape))
    )
