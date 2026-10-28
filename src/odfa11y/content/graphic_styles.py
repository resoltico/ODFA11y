# SPDX-License-Identifier: MPL-2.0
"""Resolve, verify and derive graphic-role styles without changing visual meaning."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, Part, qn
from odfa11y.report import Location, rules

from .text import reading_context_path, visible_words
from .xml import protected_xml

if TYPE_CHECKING:
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
        style_name = shape.get(qn(ns, "style-name"))
        names = ([style_name] if style_name else []) + shape.get(qn(ns, "class-names"), "").split()
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
    location = Location.named(
        reading_context_path(shape), "frame", shape.get(qn("draw", "name"), "")
    )
    if problem:
        report.add(rules.GRAPHIC001, problem, location=location)
        return False
    if role.decorative and any(
        (shape.findtext(tag, namespaces=NS) or "").strip() for tag in ("svg:title", "svg:desc")
    ):
        report.add(rules.GRAPHIC002, location=location)
    return role.decorative


PREFIX = "ODFA11yRole_"


STYLE_ATTRIBUTES = tuple(
    qn(ns, key) for ns in ("draw", "presentation") for key in ("style-name", "class-names")
)


def normalized_role_attributes(document: OdfDocument, shape: etree._Element) -> dict[str, str]:
    """Recover original references only after proving the generated style's derivation.

    Returns
    -------
    dict[str, str]
        Original style references only when the role derivation is proven.

    """
    attrs = {attr: shape.get(attr, "") for attr in STYLE_ATTRIBUTES if shape.get(attr) is not None}
    generated = [
        token for value in attrs.values() for token in value.split() if token.startswith(PREFIX)
    ]
    if len(generated) != 1:
        return attrs
    try:
        return _proven_role_attributes(document, shape, attrs, generated[0])
    except ValueError, KeyError, TypeError:
        return attrs


def _proven_role_attributes(
    document: OdfDocument, shape: etree._Element, attrs: dict[str, str], name: str
) -> dict[str, str]:
    encoded = name.removeprefix(PREFIX).rsplit("_", 1)[0]
    original = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if not isinstance(original, dict) or any(
        k not in STYLE_ATTRIBUTES or not isinstance(v, str) for k, v in original.items()
    ):
        return attrs
    shadow = deepcopy(shape)
    for attr in STYLE_ATTRIBUTES:
        shadow.attrib.pop(attr, None)
    shadow.attrib.update(original)
    catalog = GraphicStyles(document)
    ns, family, names = catalog.context(shadow)
    expected = (
        deepcopy(catalog.style(family, names[-1])) if names else etree.Element(qn("style", "style"))
    )
    expected.set(qn("style", "name"), name)
    expected.set(qn("style", "family"), family)
    generated = catalog.automatic.get((family, name), [])
    if len(generated) != 1:
        return attrs
    properties = generated[0].findall("style:graphic-properties", NS)
    if len(properties) != 1 or properties[0].get(ROLE) not in {"true", "false"}:
        return attrs
    if document.tree(Part.CONTENT).getroot().get(qn("office", "version")) != "1.4":
        return attrs
    actual = deepcopy(generated[0])
    for node in (expected, actual):
        props = node.find("style:graphic-properties", NS)
        if props is not None:
            props.attrib.pop(ROLE, None)
            if not props.attrib and not len(props):
                node.remove(props)
    applied = dict(original)
    attribute = (
        qn(ns, "class-names") if original.get(qn(ns, "class-names")) else qn(ns, "style-name")
    )
    applied[attribute] = (
        (original.get(attribute, "") + " " + name).strip()
        if attribute.endswith("class-names")
        else name
    )
    if attrs == applied and _style_signature(actual) == _style_signature(expected):
        return original
    return attrs


def normalized_graphic_tree(document: OdfDocument, root: etree._Element) -> etree._Element:
    """Copy content, restoring only proven role derivations to original references.

    Returns
    -------
    etree._Element
        A copy with proven style references restored.

    """
    clone = deepcopy(root)
    for source, target in zip(root.iter(), clone.iter(), strict=True):
        if any(source.get(attr) is not None for attr in STYLE_ATTRIBUTES):
            attributes = normalized_role_attributes(document, source)
            for attr in STYLE_ATTRIBUTES:
                target.attrib.pop(attr, None)
            target.attrib.update(attributes)
    return clone


def graphic_style_fingerprint(document: OdfDocument, shape: etree._Element) -> str:
    """Bind referenced style definitions and default visual properties.

    Returns
    -------
    str
        A digest that changes when authored style properties change.

    """
    catalog = GraphicStyles(document)
    shadow = normalized_graphic_tree(document, shape)
    return _style_facts(catalog, shadow)


def _style_facts(catalog: GraphicStyles, shadow: etree._Element) -> str:
    if catalog.scope_problem:
        raise ValueError(catalog.scope_problem)
    if shadow.tag == qn("draw", "page"):
        family = "drawing-page"
        names = [name] if (name := shadow.get(qn("draw", "style-name"))) else []
    else:
        _ns, family, names = catalog.context(shadow)
    defaults = catalog.defaults.get(family, [])
    if len(defaults) > 1:
        message = "Graphic default style is ambiguous."
        raise ValueError(message)
    facts = [_visual_style_xml(style) for style in defaults]
    for source_name in names:
        name = source_name
        style = catalog.style(family, name)
        seen: set[etree._Element] = set()
        while True:
            if style in seen:
                message = "Graphic visual style inheritance contains a cycle."
                raise ValueError(message)
            seen.add(style)
            facts.append(_visual_style_xml(style))
            parent = style.get(qn("style", "parent-style-name"))
            if not parent:
                break
            style = catalog.style(family, parent, common=True)
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]


def _visual_style_xml(style: etree._Element) -> str:
    if style.find("style:map", NS) is not None:
        message = "Conditional graphic style mapping is not established."
        raise ValueError(message)
    return protected_xml(style)


def _style_signature(style: etree._Element) -> list[object]:
    return [
        (
            node.tag,
            len(node),
            sorted(node.attrib.items()),
            node.text,
            node.tail,
            [
                (
                    attribute,
                    [
                        (prefix, uri)
                        for prefix, uri in node.nsmap.items()
                        if prefix and f"{prefix}:" in value
                    ],
                )
                for attribute, value in sorted(node.attrib.items())
            ],
        )
        for node in style.iter()
    ]


class GraphicRoleEditor(GraphicStyles):
    """Derive isolated role styles from an established graphic style catalog."""

    def derived(self, shape: etree._Element, *, decorative: bool) -> tuple[str, etree._Element]:
        """Clone the final cascade layer, retaining a legal common parent.

        Returns
        -------
        tuple[str, etree._Element]
            The namespace and detached target-specific style.

        """
        original = normalized_role_attributes(self.document, shape)
        shadow = deepcopy(shape)
        for attr in STYLE_ATTRIBUTES:
            shadow.attrib.pop(attr, None)
        shadow.attrib.update(original)
        ns, family, names = self.context(shadow)
        style = (
            deepcopy(self.style(family, names[-1]))
            if names
            else etree.Element(qn("style", "style"))
        )
        encoded = (
            base64
            .urlsafe_b64encode(json.dumps(original, sort_keys=True).encode())
            .decode()
            .rstrip("=")
        )
        name = (
            PREFIX
            + encoded
            + "_"
            + hashlib.sha256(shape.getroottree().getpath(shape).encode()).hexdigest()[:12]
        )
        style.set(qn("style", "name"), name)
        style.set(qn("style", "family"), family)
        props = style.find("style:graphic-properties", NS)
        if props is None:
            props = etree.Element(qn("style", "graphic-properties"))
            style.insert(0, props)
        props.set(ROLE, str(decorative).lower())
        return ns, style

    def set_role(self, shape: etree._Element, *, decorative: bool) -> bool:
        """Apply an isolated role; reuse only a proven earlier derivation.

        Returns
        -------
        bool
            Whether the source role changed.

        Raises
        ------
        ValueError
            The source context or supplied decision cannot be established safely.

        """
        if self.role(shape).decorative == decorative:
            return False
        problem = self.change_problem(shape, decorative=decorative)
        if problem:
            raise ValueError(problem)
        ns, style = self.derived(shape, decorative=decorative)
        name = style.get(qn("style", "name"), "")
        family = style.get(qn("style", "family"), "")
        if self.common.get((family, name)):
            message = "Generated role style name collides with an authored common style."
            raise ValueError(message)
        found = self.automatic.get((family, name), [])
        if found:
            problem = self._existing_problem(shape, style, found)
            if problem:
                raise ValueError(problem)
            props = found[0].find("style:graphic-properties", NS)
            if props is None:
                props = etree.SubElement(found[0], qn("style", "graphic-properties"))
            props.set(ROLE, str(decorative).lower())
        else:
            self._adopt(style)
        original = normalized_role_attributes(self.document, shape)
        for attr in STYLE_ATTRIBUTES:
            shape.attrib.pop(attr, None)
        shape.attrib.update(original)
        if shape.get(qn(ns, "class-names")):
            shape.set(qn(ns, "class-names"), shape.get(qn(ns, "class-names"), "") + " " + name)
        else:
            shape.set(qn(ns, "style-name"), name)
        return True

    def change_problem(self, shape: etree._Element, *, decorative: bool) -> str | None:
        """Preflight target derivation reuse before any edit.

        Returns
        -------
        str | None
            A collision/shared-reference refusal, or None for an isolated derivation.

        """
        if self.role(shape).decorative == decorative:
            return None
        if not any(
            value.split() for value in normalized_role_attributes(self.document, shape).values()
        ):
            return "Unstyled graphic placement and wrapping are unestablished; role edits refuse."
        _ns, style = self.derived(shape, decorative=decorative)
        key = (style.get(qn("style", "family"), ""), style.get(qn("style", "name"), ""))
        if self.common.get(key):
            return "Generated role style name collides with an authored common style."
        found = self.automatic.get(key, [])
        return self._existing_problem(shape, style, found) if found else None

    def _existing_problem(
        self, shape: etree._Element, style: etree._Element, found: list[etree._Element]
    ) -> str | None:
        if len(found) != 1:
            return "Generated graphic style name is ambiguous."
        expected, existing = deepcopy(style), deepcopy(found[0])
        for node in (expected, existing):
            props = node.find("style:graphic-properties", NS)
            if props is not None:
                props.attrib.pop(ROLE, None)
        if _style_signature(expected) != _style_signature(existing):
            return "Generated graphic style name belongs to unproven authored content."
        name = style.get(qn("style", "name"), "")
        if any(
            node is not shape
            and any(name in node.get(attribute, "").split() for attribute in STYLE_ATTRIBUTES)
            for node in self.document.tree(Part.CONTENT).getroot().iter()
        ):
            return "A role derivation referenced by another object cannot be edited."
        return None

    def _adopt(self, style: etree._Element) -> None:
        family = style.get(qn("style", "family"), "")
        name = style.get(qn("style", "name"), "")
        root = self.document.tree(Part.CONTENT).getroot()
        auto = root.find("office:automatic-styles", NS)
        if auto is None:
            auto = etree.Element(qn("office", "automatic-styles"))
            body = root.find("office:body", NS)
            root.insert(root.index(body) if body is not None else len(root), auto)
        auto.append(style)
        self.automatic[family, name] = [style]
