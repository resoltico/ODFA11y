# SPDX-License-Identifier: MPL-2.0
"""Reviewed native link descriptions, preserving labels and target names."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from odfa11y.adapter import Outcome, Status
from odfa11y.decisions import OpenDecision
from odfa11y.decisions.kinds import LINK_DESCRIPTION
from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import Location

from .graphic_identity import SHAPE_TAGS, GraphicIdentity
from .graphic_style_identity import (
    normalized_graphic_tree,
)
from .text import eligible_text_node, reading_context_path, visible_words
from .xml import protected_xml

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lxml import etree

    from odfa11y.odf import OdfDocument

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
LINK_TAGS = (qn("text", "a"), qn("draw", "a"))


@dataclass(frozen=True, slots=True)
class LinkDescription:
    """A supplied nonblank office:title bound to a reviewed source link."""

    description: str
    fingerprint: str


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
    identity = link.get(XML_ID) if link.tag == qn("draw", "a") else None
    return (
        Location(f"{reading_context_path(link)}/link[id={quote(identity, safe='')}]")
        if identity
        else Location.indexed(reading_context_path(link), "link", index)
    )


def link_fingerprint(document: OdfDocument, link: etree._Element) -> str:
    """Bind content, href, Name and geometry while permitting reviewed alternative metadata.

    Returns
    -------
    str
        The reviewed protected source identity.

    """
    clone = normalized_graphic_tree(document, link)
    content = protected_xml(
        clone,
        omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
        omitted_element_attributes={tag: (qn("office", "title"),) for tag in LINK_TAGS},
    )
    shapes = [node for node in link.iter() if node.tag in SHAPE_TAGS]
    identity = GraphicIdentity(document, shapes)
    graphics = identity.fingerprint(shapes)
    legal_id = link.tag == qn("draw", "a") and link.get(XML_ID)
    facts = (
        content,
        graphics,
        identity.logical_position(link),
        None if legal_id else len(document_links(document)),
    )
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]


def link_has_description(link: etree._Element) -> bool:
    """Read normative label, office:title and graphic alternatives, never office:name.

    Returns
    -------
    bool
        Whether normative source description fields supply a purpose.

    """
    return bool(
        visible_words(link)
        or link.get(qn("office", "title"), "").strip()
        or any(
            (node.text or "").strip()
            for node in select_elements(link, ".//svg:title | .//svg:desc")
        )
    )


@dataclass(frozen=True, slots=True)
class LinkEditor:
    """Preflight every exact target before setting office:title."""

    entries: Mapping[str, LinkDescription]
    name: str

    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        """Apply the complete description operation, or refuse without mutation.

        Returns
        -------
        tuple[Outcome, ...]
            Per-target outcomes; any refusal prevents all edits.

        """
        counts = Counter(
            node.get(XML_ID)
            for node in document.tree(Part.CONTENT).getroot().iter()
            if node.get(XML_ID)
        )
        available: dict[str, list[etree._Element]] = {}
        for index, link in enumerate(document_links(document), 1):
            target = link_location(link, index).path
            available.setdefault(target, []).extend(
                [link] * min(2, counts.get(link.get(XML_ID), 1))
            )
        decisions = []
        failures = []
        for target, entry in self.entries.items():
            links = available.get(target, [])
            problem = _link_problem(document, links, entry)
            if problem:
                failures.append(Outcome(self.name, Status.FAILED, problem, key=target))
            else:
                decisions.append((target, links[0], entry))
        if failures:
            return tuple(failures)
        outcomes = []
        for target, link, entry in decisions:
            changed = link.get(qn("office", "title")) != entry.description
            if changed:
                link.set(qn("office", "title"), entry.description)
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if changed else Status.UNCHANGED,
                    "Applied source link description."
                    if changed
                    else "Source link description already matches.",
                    key=target,
                    count=int(changed),
                )
            )
        return tuple(outcomes)


def _link_problem(
    document: OdfDocument, links: list[etree._Element], entry: LinkDescription
) -> str | None:
    problem = None
    if not isinstance(entry.description, str) or not entry.description.strip():
        problem = "A supplied link description must be a nonblank string."
    elif not isinstance(entry.fingerprint, str) or not entry.fingerprint:
        problem = "A link description requires a reviewed fingerprint."
    elif len(links) != 1:
        problem = "The exact logical link target must resolve to one source link."
    elif any(
        ancestor.get(qn("table", attr), "1") != "1"
        for ancestor in links[0].iterancestors()
        for attr in ("number-rows-repeated", "number-columns-repeated")
    ):
        problem = "Repeated link targets do not establish a unique logical link identity."
    elif problem := GraphicIdentity(document, ()).style_problem(links[0]):
        return problem
    elif link_fingerprint(document, links[0]) != entry.fingerprint:
        problem = "The source link changed since this decision was reviewed."
    return problem


def link_decision(
    document: OdfDocument, link: etree._Element, index: int, rule_id: str
) -> OpenDecision:
    """Describe one reviewed link without hiding its identity in diagnostic details.

    Returns
    -------
    OpenDecision
        A source-bound link-description question.

    """
    return OpenDecision(
        LINK_DESCRIPTION,
        link_location(link, index),
        link_fingerprint(document, link),
        {"description": link.get(qn("office", "title")), "href": link.get(qn("xlink", "href"))},
        (rule_id,),
    )
