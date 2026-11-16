# SPDX-License-Identifier: MPL-2.0
"""Resolve, verify and derive graphic-role styles without changing visual meaning."""

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Annotated

from lxml import etree

from odfa11y.concepts.text import reading_context_path, visible_words
from odfa11y.contracts import Choices
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import NS, Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Attributes, Container, XmlChange
from odfa11y.odf.canonical import protected_xml
from odfa11y.odf.styles import (
    GeneratedStyle,
    StyleNormalization,
    StyleResolver,
    adopt_style,
    generated_binding,
    generated_prefix,
    normalize_generated,
)
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

ROLE = xml_names.DRAW_DECORATIVE


@dataclass(frozen=True, slots=True)
class GraphicRole:
    """An established effective role, or a reason it cannot be established."""

    decorative: bool = False
    problem: str | None = None
    declared: bool = False


class GraphicRoles:
    """Resolve common parents separately from content automatic styles."""

    def __init__(self, document: OdfDocument) -> None:
        self.document = document
        self.resolver = StyleResolver.for_document(document)
        self.common = self.resolver._common
        self.automatic = self.resolver._automatic
        self.defaults = self.resolver._defaults
        self.scope_problem = " ".join(self.resolver._scope_problems) or None

    def resolve(self, family: str, name: str, *, common: bool = False) -> etree._Element:
        style = self.resolver.resolve(family, name, common=common)
        if style is None:
            message = f"Graphic style {name!r} is missing in {family!r} scope."
            raise DocumentRefusal(message)
        return style

    def chain_role(self, node: etree._Element, family: str) -> str | None:
        """Read explicit graphic roles over the shared legal inheritance chain."""
        value = None
        for style in self.resolver.chain_from(family, node):
            if style.find("style:map", NS) is not None:
                message = "Conditional graphic style mapping is not established."
                raise DocumentRefusal(message)
            properties = style.findall("style:graphic-properties", NS)
            if len(properties) > 1:
                message = "Graphic property declarations are ambiguous."
                raise DocumentRefusal(message)
            declared = properties[0].get(ROLE) if properties else None
            if declared is None:
                continue
            if (
                style.getroottree().getroot().get(xml_names.OFFICE_VERSION) != "1.4"
                or self.document.tree(Part.CONTENT).getroot().get(xml_names.OFFICE_VERSION) != "1.4"
            ):
                message = "Native decorative declarations require ODF 1.4 source semantics."
                raise DocumentRefusal(message)
            if declared not in {"true", "false"}:
                message = "Graphic decorative property is not a boolean."
                raise DocumentRefusal(message)
            value = declared
        return value

    @staticmethod
    def context(shape: etree._Element) -> tuple[str, str, list[str]]:
        """Establish one graphic or presentation cascade; mixed cascades refuse.

        Returns
        -------
        tuple[str, str, list[str]]
            Namespace, style family and the ordered cascade.

        Raises
        ------
        DocumentRefusal
            The source context or supplied decision cannot be established safely.

        """
        active = [
            ns
            for ns in ("draw", "presentation")
            if any(shape.get(qn(ns, attr)) for attr in ("style-name", "class-names"))
        ]
        if len(active) > 1:
            msg = "Mixed graphic/presentation style precedence is not established."
            raise DocumentRefusal(msg)
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
        except DocumentRefusal as error:
            return GraphicRole(problem=str(error))

    def _role_value(self, shape: etree._Element) -> str | None:
        if self.scope_problem:
            raise DocumentRefusal(self.scope_problem)
        _ns, family, names = self.context(shape)
        defaults = self.defaults.get(family, [])
        if len(defaults) > 1:
            message = "Graphic default style is ambiguous."
            raise DocumentRefusal(message)
        value = self.chain_role(defaults[0], family) if defaults else None
        for name in names:
            explicit = self.chain_role(self.resolve(family, name), family)
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
    return GraphicRoles(document).role(shape)


def decorative_problem(shape: etree._Element) -> str | None:
    """Refuse group edits, text and interactive contexts without inferring meaning.

    Returns
    -------
    str | None
        The reason decorative intent is unsafe, or None.

    """
    if shape.tag == xml_names.DRAW_G:
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
            xml_names.DRAW_CONTROL,
            xml_names.DRAW_A,
            xml_names.TEXT_A,
            xml_names.OFFICE_EVENT_LISTENERS,
            xml_names.PRESENTATION_EVENT_LISTENER,
        }
        or (
            node.get(xml_names.XLINK_HREF)
            and node.tag
            not in {xml_names.DRAW_IMAGE, xml_names.DRAW_OBJECT, xml_names.DRAW_OBJECT_OLE}
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
    if shape.tag == xml_names.DRAW_G and role.declared:
        problem = problem or "Group graphic roles require individual leaf semantic review."
    if role.decorative:
        problem = problem or decorative_problem(shape)
    location = Location.named(
        reading_context_path(shape), "frame", shape.get(xml_names.DRAW_NAME, "")
    )
    if problem:
        report.raise_(rules.GRAPHIC003, problem, location=location)
        return False
    if role.decorative and any(
        (shape.findtext(tag, namespaces=NS) or "").strip() for tag in ("svg:title", "svg:desc")
    ):
        report.raise_(rules.GRAPHIC004, location=location)
    return role.decorative


PREFIX = generated_prefix("graphic-role")


STYLE_ATTRIBUTES = tuple(
    qn(ns, key) for ns in ("draw", "presentation") for key in ("style-name", "class-names")
)


@dataclass(frozen=True, slots=True)
class RoleBinding:
    original: Mapping[Annotated[str, Choices(STYLE_ATTRIBUTES)], str]
    context: str


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
    except DocumentRefusal, ValueError, KeyError, TypeError:
        return attrs


def _proven_role_attributes(
    document: OdfDocument, shape: etree._Element, attrs: dict[str, str], name: str
) -> dict[str, str]:
    binding = generated_binding(name, "graphic-role", RoleBinding)
    original = dict(binding.original)
    shadow = deepcopy(shape)
    for attr in STYLE_ATTRIBUTES:
        shadow.attrib.pop(attr, None)
    shadow.attrib.update(original)
    catalog = GraphicRoles(document)
    ns, family, names = catalog.context(shadow)
    base = catalog.resolve(family, names[-1]) if names else None
    expected = catalog.resolver.derive(family, base, purpose="graphic-role", binding=binding)
    generated = catalog.automatic.get((family, name), [])
    if len(generated) != 1:
        return attrs
    properties = generated[0].findall("style:graphic-properties", NS)
    if len(properties) != 1 or properties[0].get(ROLE) not in {"true", "false"}:
        return attrs
    if document.tree(Part.CONTENT).getroot().get(xml_names.OFFICE_VERSION) != "1.4":
        return attrs
    applied = dict(original)
    attribute = (
        qn(ns, "class-names") if original.get(qn(ns, "class-names")) else qn(ns, "style-name")
    )
    applied[attribute] = (
        (original.get(attribute, "") + " " + name).strip()
        if attribute.endswith("class-names")
        else name
    )
    if attrs == applied and catalog.resolver.is_generated(
        generated[0], expected, ignored={xml_names.STYLE_GRAPHIC_PROPERTIES: (ROLE,)}
    ):
        return original
    return attrs


def graphic_normalization(document: OdfDocument) -> StyleNormalization:
    def restore(source: etree._Element, current: Mapping[str, str]) -> Mapping[str, str] | None:
        if any(source.get(attribute) is not None for attribute in STYLE_ATTRIBUTES):
            return normalized_role_attributes(document, source)
        return None

    return StyleNormalization(STYLE_ATTRIBUTES, restore)


def graphic_style_fingerprint(document: OdfDocument, shape: etree._Element) -> str:
    """Bind referenced style definitions and default visual properties.

    Returns
    -------
    str
        A digest that changes when authored style properties change.

    """
    catalog = GraphicRoles(document)
    shadow = normalize_generated(shape, graphic_normalization(document))
    return _style_facts(catalog, shadow)


def _style_facts(catalog: GraphicRoles, shadow: etree._Element) -> Fingerprint:
    if catalog.scope_problem:
        raise DocumentRefusal(catalog.scope_problem)
    if shadow.tag == xml_names.DRAW_PAGE:
        family = "drawing-page"
        names = [name] if (name := shadow.get(xml_names.DRAW_STYLE_NAME)) else []
    else:
        _ns, family, names = catalog.context(shadow)
    defaults = catalog.defaults.get(family, [])
    if len(defaults) > 1:
        message = "Graphic default style is ambiguous."
        raise DocumentRefusal(message)
    facts = [_visual_style_xml(style) for style in defaults]
    for source_name in names:
        # Preserve source-first fingerprint ordering while sharing common-parent resolution.
        facts.extend(
            _visual_style_xml(style)
            for style in reversed(catalog.resolver.chain(family, source_name))
        )
    return Fingerprint.of(json.dumps(facts, sort_keys=True).encode())


def _visual_style_xml(style: etree._Element) -> str:
    if style.find("style:map", NS) is not None:
        message = "Conditional graphic style mapping is not established."
        raise DocumentRefusal(message)
    return protected_xml(style)


class GraphicRoleEditor(GraphicRoles):
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
        base = self.resolve(family, names[-1]) if names else None
        binding = RoleBinding(
            original, hashlib.sha256(shape.getroottree().getpath(shape).encode()).hexdigest()[:12]
        )
        style = self.resolver.derive(family, base, purpose="graphic-role", binding=binding).element
        props = style.find("style:graphic-properties", NS)
        if props is None:
            props = etree.Element(xml_names.STYLE_GRAPHIC_PROPERTIES)
            style.insert(0, props)
        props.set(ROLE, str(decorative).lower())
        return ns, style

    def set_role(self, shape: etree._Element, *, decorative: bool) -> XmlChange:
        """Apply an isolated role; reuse only a proven earlier derivation.

        Returns
        -------
        bool
            Whether the source role changed.

        Raises
        ------
        DocumentRefusal
            The source context or supplied decision cannot be established safely.

        """
        if self.role(shape).decorative == decorative:
            return XmlChange(False)
        problem = self.change_problem(shape, decorative=decorative)
        if problem:
            raise DocumentRefusal(problem)
        ns, style = self.derived(shape, decorative=decorative)
        name = style.get(xml_names.STYLE_NAME, "")
        family = style.get(xml_names.STYLE_FAMILY, "")
        if self.common.get((family, name)):
            message = "Generated role style name collides with an authored common style."
            raise DocumentRefusal(message)
        found = self.automatic.get((family, name), [])
        allowance = Allowance((Attributes(Part.CONTENT, shape, frozenset(STYLE_ATTRIBUTES)),))
        if found:
            problem = self._existing_problem(shape, style, found)
            if problem:
                raise DocumentRefusal(problem)
            props = found[0].find("style:graphic-properties", NS)
            if props is None:
                props = etree.SubElement(found[0], xml_names.STYLE_GRAPHIC_PROPERTIES)
                allowance |= Allowance((Container(Part.CONTENT, props),))
            allowance |= Allowance((Attributes(Part.CONTENT, props, frozenset({ROLE})),))
            props.set(ROLE, str(decorative).lower())
        else:
            allowance |= self._adopt(style)
        original = normalized_role_attributes(self.document, shape)
        for attr in STYLE_ATTRIBUTES:
            shape.attrib.pop(attr, None)
        shape.attrib.update(original)
        if shape.get(qn(ns, "class-names")):
            shape.set(qn(ns, "class-names"), shape.get(qn(ns, "class-names"), "") + " " + name)
        else:
            shape.set(qn(ns, "style-name"), name)
        return XmlChange(True, allowance)

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
        key = (style.get(xml_names.STYLE_FAMILY, ""), style.get(xml_names.STYLE_NAME, ""))
        if self.common.get(key):
            return "Generated role style name collides with an authored common style."
        found = self.automatic.get(key, [])
        return self._existing_problem(shape, style, found) if found else None

    def _existing_problem(
        self, shape: etree._Element, style: etree._Element, found: list[etree._Element]
    ) -> str | None:
        if len(found) != 1:
            return "Generated graphic style name is ambiguous."
        expected = GeneratedStyle(style.get(xml_names.STYLE_NAME, ""), style)
        if not self.resolver.is_generated(
            found[0], expected, ignored={xml_names.STYLE_GRAPHIC_PROPERTIES: (ROLE,)}
        ):
            return "Generated graphic style name belongs to unproven authored content."
        name = style.get(xml_names.STYLE_NAME, "")
        if any(
            node is not shape
            and any(name in node.get(attribute, "").split() for attribute in STYLE_ATTRIBUTES)
            for node in self.document.tree(Part.CONTENT).getroot().iter()
        ):
            return "A role derivation referenced by another object cannot be edited."
        return None

    def _adopt(self, style: etree._Element) -> Allowance:
        return adopt_style(self.resolver, style)
