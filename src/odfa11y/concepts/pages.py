# SPDX-License-Identifier: MPL-2.0
"""ODF drawing-page identities, descriptions, navigation and protected content."""

import json
from collections import Counter

from lxml import etree

from odfa11y.concepts.graphic_identity import (
    SHAPE_TAGS,
    GraphicIdentity,
    graphic_style_dependencies,
)
from odfa11y.concepts.graphic_styles import graphic_normalization
from odfa11y.concepts.graphics import set_description
from odfa11y.decisions import Decision
from odfa11y.decisions.answers import PageMetadataAnswer, PageNavigationAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import Part, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Attributes, TextFields
from odfa11y.odf.canonical import protected_xml
from odfa11y.odf.styles import normalize_generated
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument

XML_ID = xml_names.XML_ID


DESCRIPTIONS = (xml_names.SVG_TITLE, xml_names.SVG_DESC)


def pages(document: OdfDocument) -> list[etree._Element]:
    """Collect body pages in source order.

    Returns
    -------
    list[etree._Element]
        Direct drawing pages, excluding notes and master pages.

    """
    return select_elements(document.tree(Part.CONTENT), "//office:body/*/draw:page")


def page_shapes(page: etree._Element) -> list[etree._Element]:
    """Collect the navigable top-level shapes of a page.

    Returns
    -------
    list[etree._Element]
        Shapes in source order; a group is one top-level navigation entry.

    """
    result = []
    for node in page:
        candidates = list(node) if node.tag == xml_names.DRAW_A else [node]
        result.extend(shape for shape in candidates if shape.tag in SHAPE_TAGS)
    return result


def shape_identity(shape: etree._Element) -> str | None:
    """Read an existing navigation identity, refusing contradictory declarations.

    Returns
    -------
    str | None
        The XML/drawing identity, or None when missing or contradictory.

    """
    xml, drawing = shape.get(XML_ID), shape.get(xml_names.DRAW_ID)
    if xml and drawing and xml != drawing:
        return None
    identity = xml or drawing
    if identity:
        try:
            name = etree.QName(identity)
        except ValueError:
            return None
        if name.namespace is not None:
            return None
    return identity


def page_fingerprint(page: etree._Element, document: OdfDocument) -> Fingerprint:
    """Bind a reviewed page to words, shape identities, geometry, notes and references.

    Returns
    -------
    str
        A digest excluding description metadata and the editable navigation list.

    """
    content = protected_xml(
        normalize_generated(page, graphic_normalization(document)),
        omitted_element_attributes={
            qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
        },
        omitted_root_attributes=(xml_names.DRAW_NAV_ORDER,),
        omitted_elements=DESCRIPTIONS,
    )
    facts = (content, graphic_style_dependencies(document, page))
    return Fingerprint.of(json.dumps(facts, sort_keys=True).encode())


def navigation_problem(
    page: etree._Element, order: tuple[str, ...], counts: Counter[str]
) -> str | None:
    """Explain an incomplete or ambiguous navigation declaration.

    Returns
    -------
    str | None
        A mechanical defect, or None for a complete globally unique list.

    """
    identities = [shape_identity(shape) for shape in page_shapes(page)]
    if None in identities or len(set(identities)) != len(identities):
        return "Every top-level shape needs an existing unique navigation identity."
    if not isinstance(order, tuple) or not all(isinstance(identity, str) for identity in order):
        return "Navigation must be a tuple of shape identity strings."
    if not order:
        return "Navigation requires at least one existing top-level shape."
    if len(set(order)) != len(order) or set(order) != set(identities):
        return "Navigation must contain every top-level shape identity exactly once."
    if any(counts[identity] != 1 for identity in order):
        return "Navigation identities must be unique across the content document."
    return None


def edit_page_metadata(document: OdfDocument, decision: Decision[PageMetadataAnswer]) -> EditResult:
    """Apply reviewed metadata to one native page."""
    page = resolved_node(document, decision)
    if problem := GraphicIdentity(document, ()).style_problem(page):
        raise DocumentRefusal(problem)
    fields = TextFields.capture(
        Part.CONTENT,
        page,
        (
            (xml_names.SVG_TITLE, decision.answer.title),
            (xml_names.SVG_DESC, decision.answer.description),
        ),
    )
    changed = set_description(page, decision.answer.title, decision.answer.description)
    return EditResult(_page_outcome(decision, changed), fields.allowance())


def edit_page_navigation(
    document: OdfDocument, decision: Decision[PageNavigationAnswer]
) -> EditResult:
    """Apply a complete order of existing globally unique shape identities."""
    page = resolved_node(document, decision)
    identities = Counter(
        identity
        for node in document.tree(Part.CONTENT).iter()
        if (identity := node.get(XML_ID) or node.get(xml_names.DRAW_ID))
    )
    if problem := GraphicIdentity(document, ()).style_problem(page):
        raise DocumentRefusal(problem)
    if problem := navigation_problem(page, decision.answer.navigation, identities):
        raise DocumentRefusal(problem)
    allowance = Allowance((Attributes(Part.CONTENT, page, frozenset({xml_names.DRAW_NAV_ORDER})),))
    value = " ".join(decision.answer.navigation)
    changed = page.get(xml_names.DRAW_NAV_ORDER) != value
    if changed:
        page.set(xml_names.DRAW_NAV_ORDER, value)
    return EditResult(_page_outcome(decision, changed), allowance)


def _page_outcome(decision: Decision, changed: bool) -> tuple[Outcome, ...]:
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            "Applied page decision." if changed else "Page decision already matches.",
            target=decision.target_path,
            count=int(changed),
        ),
    )
