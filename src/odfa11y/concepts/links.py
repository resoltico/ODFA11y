# SPDX-License-Identifier: MPL-2.0
"""Reviewed native link descriptions, preserving labels and target names."""

import json
from collections import Counter
from urllib.parse import quote

lazy from lxml import etree

from odfa11y.concepts.graphic_identity import SHAPE_TAGS, GraphicIdentity
from odfa11y.concepts.graphic_styles import normalized_graphic_tree
from odfa11y.concepts.text import eligible_text_node, reading_context_path, visible_words
from odfa11y.concepts.xml import protected_xml
from odfa11y.decisions import Decision, DecisionKind, OpenDecision
from odfa11y.decisions.answers import LinkDescriptionAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import Part, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.odf import OdfDocument

XML_ID = xml_names.XML_ID
LINK_TAGS = (xml_names.TEXT_A, xml_names.DRAW_A)


def document_links(document: OdfDocument) -> list[etree._Element]:
    """Read current body links in deterministic order, excluding unsupported text contexts.

    Returns
    -------
    list[etree._Element]
        Eligible links in deterministic source order.

    """
    return [
        node
        for node in select_elements(
            document.tree(Part.CONTENT), "//office:body//text:a | //office:body//draw:a"
        )
        if eligible_text_node(node)
    ]


def link_location(link: etree._Element, index: int) -> Location:
    """Use a legal draw:a XML identity where available, otherwise a one-based ordinal.

    Returns
    -------
    Location
        The exact logical source target.

    """
    identity = link.get(XML_ID) if link.tag == xml_names.DRAW_A else None
    return (
        Location(f"{reading_context_path(link)}/link[id={quote(identity, safe='')}]")
        if identity
        else Location.indexed(reading_context_path(link), "link", index)
    )


def link_fingerprint(document: OdfDocument, link: etree._Element) -> Fingerprint:
    """Bind content, href, Name and geometry while permitting reviewed alternative metadata.

    Returns
    -------
    str
        The reviewed protected source identity.

    """
    clone = normalized_graphic_tree(document, link)
    content = protected_xml(
        clone,
        omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
        omitted_element_attributes={tag: (xml_names.OFFICE_TITLE,) for tag in LINK_TAGS},
    )
    shapes = [node for node in link.iter() if node.tag in SHAPE_TAGS]
    identity = GraphicIdentity(document, shapes)
    graphics = identity.fingerprint(shapes)
    legal_id = link.tag == xml_names.DRAW_A and link.get(XML_ID)
    facts = (
        content,
        graphics,
        identity.logical_position(link),
        None if legal_id else len(document_links(document)),
    )
    return Fingerprint.of(json.dumps(facts, sort_keys=True).encode())


def link_has_description(link: etree._Element) -> bool:
    """Read normative label, office:title and graphic alternatives, never office:name.

    Returns
    -------
    bool
        Whether normative source description fields supply a purpose.

    """
    return bool(
        visible_words(link)
        or link.get(xml_names.OFFICE_TITLE, "").strip()
        or any(
            (node.text or "").strip()
            for node in select_elements(link, ".//svg:title | .//svg:desc")
        )
    )


def link_decision(
    document: OdfDocument, link: etree._Element, index: int, kind: DecisionKind
) -> OpenDecision:
    """Describe one reviewed link without hiding its identity in diagnostic details.

    Returns
    -------
    OpenDecision
        A source-bound link-description question.

    """
    return OpenDecision(
        kind,
        Target(
            (link_location(link, index)).path,
            Fingerprint(link_fingerprint(document, link)),
        ),
        {"description": link.get(xml_names.OFFICE_TITLE), "href": link.get(xml_names.XLINK_HREF)},
    )


def edit_link(
    document: OdfDocument, decision: Decision[LinkDescriptionAnswer]
) -> tuple[Outcome, ...]:
    """Set a reviewed link description without changing its label or destination."""
    link = resolved_node(document, decision)
    identities = Counter(
        node.get(XML_ID) for node in document.tree(Part.CONTENT).iter() if node.get(XML_ID)
    )
    if link.get(XML_ID) and identities[link.get(XML_ID)] != 1:
        message = "The exact logical link target must resolve to one source link."
        raise DocumentRefusal(message)
    if any(
        ancestor.get(qn("table", attr), "1") != "1"
        for ancestor in link.iterancestors()
        for attr in ("number-rows-repeated", "number-columns-repeated")
    ):
        message = "Repeated link targets do not establish a unique logical link identity."
        raise DocumentRefusal(message)
    if problem := GraphicIdentity(document, ()).style_problem(link):
        raise DocumentRefusal(problem)
    changed = link.get(xml_names.OFFICE_TITLE) != decision.answer.description
    if changed:
        link.set(xml_names.OFFICE_TITLE, decision.answer.description)
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            "Applied source link description."
            if changed
            else "Source link description already matches.",
            target=decision.target_path,
            count=int(changed),
        ),
    )
