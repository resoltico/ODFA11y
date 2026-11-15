# SPDX-License-Identifier: MPL-2.0
"""Audit presentation and drawing pages, content, descriptions and explicit navigation."""

from collections import Counter

lazy from lxml import etree

from odfa11y.concepts import (
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
from odfa11y.concepts.kinds import (
    GRAPHIC_ALTERNATIVE,
    LINK_DESCRIPTION,
    PAGE_METADATA,
    PAGE_NAVIGATION,
)
from odfa11y.decisions import OpenDecision
from odfa11y.odf import NS, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import FactKeys, Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.families.pages.profiles import PageProfile
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

XML_ID = xml_names.XML_ID


def audit_document(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    """Report semantic defects without executing scripts, links or rendering."""
    available = pages(document)
    names = Counter(page.get(xml_names.DRAW_NAME) for page in available)
    identities = Counter(
        identity
        for node in document.tree(Part.CONTENT).iter()
        if (identity := node.get(XML_ID) or node.get(xml_names.DRAW_ID))
    )
    report.facts[FactKeys.PAGE_COUNT] = len(available)
    if not available:
        report.raise_(rules.PAGE001, location=Location(Part.CONTENT))
    for index, page in enumerate(available, 1):
        _audit_page(document, page, index, names, identities, report=report)
    _graphics(document, report, profile)
    _links(document, report)
    _review_content(document, report, profile)


def _audit_page(
    document: OdfDocument,
    page: etree._Element,
    index: int,
    names: Counter[str | None],
    identities: Counter[str],
    *,
    report: Report,
) -> None:
    name = page.get(xml_names.DRAW_NAME)
    location = page_location(page, index)
    fingerprint = page_fingerprint(page, document)
    details = {"page": name}
    if not name or names[name] != 1:
        report.raise_(rules.PAGE001, location=location)
    if not (page.findtext("svg:title", namespaces=NS) or "").strip():
        decision = (
            OpenDecision(
                PAGE_METADATA,
                Target(location.path, Fingerprint(fingerprint)),
                {
                    "title": page.findtext("svg:title", namespaces=NS),
                    "description": page.findtext("svg:desc", namespaces=NS),
                },
            )
            if not name or names[name] == 1
            else None
        )
        report.raise_(rules.PAGE002, location=location, details=details, decision=decision)
    order = page.get(xml_names.DRAW_NAV_ORDER)
    shapes = page_shapes(page)
    supplied_ids = [shape.get(XML_ID) or shape.get(xml_names.DRAW_ID) for shape in shapes]
    details["shape_identities"] = supplied_ids
    problem = (
        navigation_problem(page, tuple(order.split()), identities) if order is not None else None
    )
    rule = (
        rules.PAGE003 if problem else rules.PAGE004 if order is None and len(shapes) > 1 else None
    )
    if rule is None:
        return
    decision = (
        OpenDecision(
            PAGE_NAVIGATION,
            Target(location.path, Fingerprint(fingerprint)),
            {
                "navigation": tuple(order.split()) if order else None,
                "available_identities": supplied_ids,
            },
        )
        if (not name or names[name] == 1)
        and all(identity and identities[identity] == 1 for identity in supplied_ids)
        else None
    )
    report.raise_(rule, problem, location=location, details=details, decision=decision)


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
        if decorative or shape.tag == xml_names.DRAW_G:
            continue
        name = shape.get(xml_names.DRAW_NAME)
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
        rule = rules.GRAPHIC003 if payload else rules.GRAPHIC005
        report.raise_(
            rule,
            location=Location(identity.target(shape)),
            details={
                "shape": name,
            },
            decision=identity.open_decision(shape, GRAPHIC_ALTERNATIVE, rule.id),
        )


def _links(document: OdfDocument, report: Report) -> None:
    links = document_links(document)
    report.facts[FactKeys.PAGE_LINK_COUNT] = len(links)
    for index, link in enumerate(links, 1):
        if not link_has_description(link):
            report.raise_(
                rules.LINK003,
                location=link_location(link, index),
                decision=link_decision(document, link, index, LINK_DESCRIPTION, rules.LINK003.id),
            )


def _review_content(document: OdfDocument, report: Report, profile: PageProfile) -> None:
    notes = select_elements(
        document.tree(Part.CONTENT),
        "//office:body//presentation:notes | //office:body//office:annotation",
    )
    if any(visible_words(note) for note in notes):
        report.raise_(
            rules.NOTE001,
            details={"content_count": sum(bool(visible_words(note)) for note in notes)},
        )
    hidden = profile.hidden_content(document)
    if hidden:
        report.raise_(rules.HIDDEN001, details=hidden)


def _skipped_shape(shape: etree._Element, profile: PageProfile) -> bool:
    return profile.skip_presentation_shapes and (
        shape.tag == xml_names.DRAW_PAGE_THUMBNAIL
        or (shape.get(xml_names.PRESENTATION_PLACEHOLDER) == "true" and not visible_words(shape))
    )
