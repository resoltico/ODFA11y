# SPDX-License-Identifier: MPL-2.0
"""ODF drawing-page identities, descriptions, navigation and protected content."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.adapter import Outcome, Status
from odfa11y.odf import Part, qn, select_elements

from .graphics import GraphicDescription, set_description
from .xml import protected_xml

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdfDocument

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
SHAPE_TAGS = (
    *(
        qn("draw", name)
        for name in (
            "frame",
            "rect",
            "ellipse",
            "line",
            "path",
            "polygon",
            "polyline",
            "regular-polygon",
            "custom-shape",
            "connector",
            "measure",
            "g",
            "caption",
            "circle",
            "page-thumbnail",
            "control",
        )
    ),
    qn("dr3d", "scene"),
)

DESCRIPTIONS = (qn("svg", "title"), qn("svg", "desc"))


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
        candidates = list(node) if node.tag == qn("draw", "a") else [node]
        result.extend(shape for shape in candidates if shape.tag in SHAPE_TAGS)
    return result


def shape_identity(shape: etree._Element) -> str | None:
    """Read an existing navigation identity, refusing contradictory declarations.

    Returns
    -------
    str | None
        The XML/drawing identity, or None when missing or contradictory.

    """
    xml, drawing = shape.get(XML_ID), shape.get(qn("draw", "id"))
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


def page_fingerprint(page: etree._Element) -> str:
    """Bind a reviewed page to words, shape identities, geometry, notes and references.

    Returns
    -------
    str
        A digest excluding description metadata and the editable navigation list.

    """
    return protected_xml(
        page, omitted_root_attributes=(qn("draw", "nav-order"),), omitted_elements=DESCRIPTIONS
    )[:16]


def page_snapshot(document: OdfDocument) -> tuple[str, ...]:
    """Protect page count, ordering and all page data outside editable metadata.

    Returns
    -------
    tuple[str, ...]
        One protected digest per page.

    """
    body = select_elements(document.tree(Part.CONTENT), "//office:body")[0]
    return (
        protected_xml(
            body,
            omitted_elements=DESCRIPTIONS,
            omitted_element_attributes={qn("draw", "page"): (qn("draw", "nav-order"),)},
        ),
    )


@dataclass(frozen=True, slots=True)
class PageDecision:
    """Explicit page metadata and a complete order of existing shape identities."""

    title: str | None = None
    description: str | None = None
    navigation: tuple[str, ...] | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class PageEditor:
    """Preflight all selected pages before editing descriptions or navigation."""

    entries: Mapping[str, PageDecision]
    name: str

    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        """Apply a complete reviewed page plan or report failures without edits.

        Returns
        -------
        tuple[Outcome, ...]
            Per-target outcomes.

        """
        available = pages(document)
        identities = Counter(
            identity
            for node in document.tree(Part.CONTENT).iter()
            if (identity := node.get(XML_ID) or node.get(qn("draw", "id")))
        )
        decisions = []
        failures = []
        for name, entry in self.entries.items():
            matches = [page for page in available if page.get(qn("draw", "name")) == name]
            problem = _problem(matches, entry, identities)
            if problem:
                failures.append(Outcome(self.name, Status.FAILED, problem, key=name))
            else:
                decisions.append((name, matches[0], entry))
        if failures:
            return tuple(failures)
        outcomes = []
        for name, page, entry in decisions:
            changed = set_description(
                document, page, GraphicDescription(entry.title, entry.description)
            )
            if entry.navigation is not None:
                value = " ".join(entry.navigation)
                if page.get(qn("draw", "nav-order")) != value:
                    document.edit(Part.CONTENT)
                    page.set(qn("draw", "nav-order"), value)
                    changed = True
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if changed else Status.UNCHANGED,
                    "Applied page decision." if changed else "Page decision already matches.",
                    key=name,
                    count=int(changed),
                )
            )
        return tuple(outcomes)


def _problem(
    matches: list[etree._Element], entry: PageDecision, counts: Counter[str]
) -> str | None:
    if len(matches) != 1:
        return "The page name must resolve to exactly one page."
    if any(
        value is not None and not isinstance(value, str)
        for value in (entry.title, entry.description, entry.fingerprint)
    ):
        return "Page title, description and fingerprint must be strings."
    page = matches[0]
    if entry.fingerprint is not None and entry.fingerprint != page_fingerprint(page):
        return "The page is no longer the object this plan was reviewed against."
    if entry.navigation is None:
        return None
    return navigation_problem(page, entry.navigation, counts)


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
