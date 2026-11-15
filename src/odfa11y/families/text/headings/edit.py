# SPDX-License-Identifier: MPL-2.0
"""Reviewed, explicit semantic heading levels with stable logical targets."""

from urllib.parse import quote

lazy from lxml import etree

from odfa11y.concepts import normalized_graphic_tree, protected_xml
from odfa11y.decisions import Decision
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.families.text.answers import HeadingLevelAnswer
from odfa11y.odf import Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument

XML_ID = xml_names.XML_ID


def heading_location(heading: etree._Element, index: int) -> Location:
    """Address a heading by XML identity, otherwise by its one-based ordinal.

    Returns
    -------
    Location
        The canonical logical heading target.

    """
    identity = heading.get(XML_ID)
    return (
        Location(f"{Part.CONTENT}/heading[id={quote(identity, safe='')}]")
        if identity
        else Location.indexed(Part.CONTENT, "heading", index)
    )


def heading_fingerprint(
    heading: etree._Element, document: OdfDocument | None = None
) -> Fingerprint:
    """Bind an outline decision to the full heading content, excluding mutable metadata.

    Returns
    -------
    str
        The stable reviewed-content digest.

    """
    return Fingerprint.from_digest(
        protected_xml(
            normalized_graphic_tree(document, heading) if document is not None else heading,
            omitted_element_attributes={
                qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
            },
            omitted_root_attributes=(xml_names.TEXT_OUTLINE_LEVEL,),
            omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
        )
    )


def edit_heading(
    document: OdfDocument, decision: Decision[HeadingLevelAnswer]
) -> tuple[Outcome, ...]:
    """Set the reviewed semantic level of one heading."""
    heading = resolved_node(document, decision)
    changed = heading.get(xml_names.TEXT_OUTLINE_LEVEL) != str(decision.answer.level)
    if changed:
        heading.set(xml_names.TEXT_OUTLINE_LEVEL, str(decision.answer.level))
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            f"Outline level {decision.answer.level}.",
            target=decision.target_path,
            count=int(changed),
        ),
    )
