# SPDX-License-Identifier: MPL-2.0
"""Resolve graphic roles and derive isolated, verifiable role styles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.odf import NS, Part, qn
from odfa11y.report import Location, rules

from .text import text_context_path, visible_words

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

ROLE = qn("draw", "decorative")


@dataclass(frozen=True, slots=True)
class GraphicRole:
    """An established effective role, or a reason it cannot be established."""

    decorative: bool = False
    problem: str | None = None
    declared: bool = False


class GraphicStyles:
    """Resolve common parents separately from content automatic styles."""

    def __init__(self, document: OdfDocument) -> None:
        self.document = document
        self.common: dict[tuple[str, str], list[etree._Element]] = {}
        self.automatic: dict[tuple[str, str], list[etree._Element]] = {}
        self.defaults: dict[str, list[etree._Element]] = {}
        self.scope_problem: str | None = None
        for part, container_tag in ((Part.STYLES, "styles"), (Part.CONTENT, "automatic-styles")):
            if not document.has(part):
                continue
            containers = document.tree(part).getroot().findall(qn("office", container_tag))
            if len(containers) > 1:
                self.scope_problem = f"Applicable office:{container_tag} container is ambiguous."
            for container in containers:
                self._index(container, automatic=container_tag == "automatic-styles")

    def _index(self, container: etree._Element, *, automatic: bool) -> None:
        for node in container:
            family = node.get(qn("style", "family"), "")
            if node.tag == qn("style", "default-style") and not automatic:
                self.defaults.setdefault(family, []).append(node)
            elif node.tag == qn("style", "style"):
                index = self.automatic if automatic else self.common
                index.setdefault((family, node.get(qn("style", "name"), "")), []).append(node)

    def style(self, family: str, name: str, *, common: bool = False) -> etree._Element:
        """Resolve a name in its legal scope, refusing ambiguity and broken references.

        Returns
        -------
        etree._Element
            The uniquely resolved style.

        Raises
        ------
        ValueError
            The source context or supplied decision cannot be established safely.

        """
        key = (family, name)
        found = (
            self.common.get(key, [])
            if common
            else self.automatic.get(key, []) or self.common.get(key, [])
        )
        if len(found) != 1:
            msg = f"Graphic style {name!r} is missing or ambiguous in {family!r} scope."
            raise ValueError(msg)
        return found[0]

    def chain_role(
        self, node: etree._Element, family: str, seen: set[etree._Element]
    ) -> str | None:
        """Read role inheritance through legal common style parents.

        Returns
        -------
        str | None
            The inherited explicit role, or None for the standard default.

        Raises
        ------
        ValueError
            The source context or supplied decision cannot be established safely.

        """
        if node in seen:
            msg = "Graphic style inheritance contains a cycle."
            raise ValueError(msg)
        seen = seen.copy()
        seen.add(node)
        if node.find("style:map", NS) is not None:
            message = "Conditional graphic style mapping is not established."
            raise ValueError(message)
        parent = node.get(qn("style", "parent-style-name"))
        inherited = (
            self.chain_role(self.style(family, parent, common=True), family, seen)
            if parent
            else None
        )
        properties = node.findall("style:graphic-properties", NS)
        if len(properties) > 1:
            message = "Graphic property declarations are ambiguous."
            raise ValueError(message)
        value = properties[0].get(ROLE) if properties else None
        if value is not None and (
            node.getroottree().getroot().get(qn("office", "version")) != "1.4"
            or self.document.tree(Part.CONTENT).getroot().get(qn("office", "version")) != "1.4"
        ):
            message = "Native decorative declarations require ODF 1.4 source semantics."
            raise ValueError(message)
        if value is not None and value not in {"true", "false"}:
            msg = "Graphic decorative property is not a boolean."
            raise ValueError(msg)
        return value if value is not None else inherited

    @staticmethod
    def context(shape: etree._Element) -> tuple[str, str, list[str]]:
        """Establish one graphic or presentation cascade; mixed cascades refuse.

        Returns
        -------
        tuple[str, str, list[str]]
            Namespace, style family and the ordered cascade.

        Raises
        ------
        ValueError
            The source context or supplied decision cannot be established safely.

        """
        active = [
            ns
            for ns in ("draw", "presentation")
            if any(shape.get(qn(ns, attr)) for attr in ("style-name", "class-names"))
        ]
        if len(active) > 1:
            msg = "Mixed graphic/presentation style precedence is not established."
            raise ValueError(msg)
        ns = active[0] if active else "draw"
        family = "graphic" if ns == "draw" else "presentation"
        names = (
            [shape.get(qn(ns, "style-name"))] if shape.get(qn(ns, "style-name")) else []
        ) + shape.get(qn(ns, "class-names"), "").split()
        return ns, family, names

    def role(self, shape: etree._Element) -> GraphicRole:
        """Resolve defaults, inheritance and ordered class overlays.

        Returns
        -------
        GraphicRole
            The established role or the unresolved reason.

        """
        try:
            value = self._role_value(shape)
            return GraphicRole(value == "true", declared=value is not None)
        except ValueError as error:
            return GraphicRole(problem=str(error))

    def _role_value(self, shape: etree._Element) -> str | None:
        if self.scope_problem:
            raise ValueError(self.scope_problem)
        _ns, family, names = self.context(shape)
        defaults = self.defaults.get(family, [])
        if len(defaults) > 1:
            message = "Graphic default style is ambiguous."
            raise ValueError(message)
        value = self.chain_role(defaults[0], family, set()) if defaults else None
        for name in names:
            explicit = self.chain_role(self.style(family, name), family, set())
            if explicit is not None:
                value = explicit
        return value


def effective_graphic_role(document: OdfDocument, shape: etree._Element) -> GraphicRole:
    """Read the established source role without changing the document.

    Returns
    -------
    GraphicRole
        The effective source declaration and any resolution problem.

    """
    return GraphicStyles(document).role(shape)


def decorative_problem(shape: etree._Element) -> str | None:
    """Refuse group edits, text and interactive contexts without inferring meaning.

    Returns
    -------
    str | None
        The reason decorative intent is unsafe, or None.

    """
    if shape.tag == qn("draw", "g"):
        return "Explicit group role edits are unsupported; review each eligible leaf."
    if visible_words(shape):
        return "A graphic containing nonblank text cannot be declared decorative."
    nodes = list(shape.iter()) + list(shape.iterancestors())
    nodes += [
        listener
        for ancestor in shape.iterancestors()
        for listener in ancestor.findall("office:event-listeners", NS)
    ]
    if any(
        node.tag
        in {
            qn("draw", "control"),
            qn("draw", "a"),
            qn("text", "a"),
            qn("office", "event-listeners"),
            qn("presentation", "event-listener"),
        }
        or (
            node.get(qn("xlink", "href"))
            and node.tag
            not in {qn("draw", "image"), qn("draw", "object"), qn("draw", "object-ole")}
        )
        for node in nodes
    ):
        return "A graphic in a control, navigation or action context cannot be decorative."
    return None


def audit_graphic_role(document: OdfDocument, shape: etree._Element, report: Report) -> bool:
    """Report role conflicts; return true only for a safe established leaf declaration.

    Returns
    -------
    bool
        Whether a safe decorative declaration removes the alternative requirement.

    """
    role = effective_graphic_role(document, shape)
    problem = role.problem
    if shape.tag == qn("draw", "g") and role.declared:
        problem = problem or "Group graphic roles require individual leaf semantic review."
    if role.decorative:
        problem = problem or decorative_problem(shape)
    location = Location.named(text_context_path(shape), "frame", shape.get(qn("draw", "name"), ""))
    if problem:
        report.add(rules.GRAPHIC001, problem, location=location)
        return False
    if role.decorative and any(
        (shape.findtext(tag, namespaces=NS) or "").strip() for tag in ("svg:title", "svg:desc")
    ):
        report.add(rules.GRAPHIC002, location=location)
    return role.decorative
