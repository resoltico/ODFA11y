# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve scoped paragraph styles and derive verifiable spacing styles."""

import base64
import binascii
import copy
import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass

from lxml import etree

from odfa11y.contracts import decode, record_dict
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import NS, Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Attributes, Container, Created
from odfa11y.odf.canonical import attribute_bindings
lazy from odfa11y.odf import OdfDocument

SPACING_ATTRIBUTES = (
    xml_names.FO_MARGIN_TOP,
    xml_names.FO_MARGIN_BOTTOM,
    xml_names.FO_LINE_HEIGHT,
    xml_names.FO_LINE_HEIGHT_AT_LEAST,
    xml_names.STYLE_CONTEXTUAL_SPACING,
)

BREAK_ATTRIBUTES = (
    xml_names.FO_BREAK_BEFORE,
    xml_names.FO_BREAK_AFTER,
    xml_names.STYLE_MASTER_PAGE_NAME,
    xml_names.STYLE_PAGE_NUMBER,
)


@dataclass(frozen=True, slots=True)
class GeneratedStyle:
    name: str
    element: etree._Element


@dataclass(frozen=True, slots=True)
class SpacingBinding:
    base: str | None


def _definition(style: etree._Element) -> tuple[object, ...]:
    """Compare expanded XML names while retaining bindings used by attribute values."""
    return tuple(
        (
            str(node.tag),
            len(node),
            tuple(sorted(node.attrib.items())),
            node.text,
            node.tail,
            attribute_bindings(node),
        )
        for node in style.iter()
    )


def generated_prefix(purpose: str) -> str:
    return "ODFA11y_" + purpose + "_"


def generated_name(purpose: str, binding: object) -> str:
    payload = json.dumps(record_dict(binding), sort_keys=True, separators=(",", ":"))
    return generated_prefix(purpose) + base64.urlsafe_b64encode(payload.encode()).decode().rstrip(
        "="
    )


def generated_binding[T](name: str, purpose: str, expected: type[T]) -> T:
    prefix = generated_prefix(purpose)
    if not name.startswith(prefix):
        message = f"Style is not a {purpose} derivation."
        raise DocumentRefusal(message)
    payload = name[len(prefix) :]
    try:
        values = json.loads(
            base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
        )
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as error:
        message = "Generated style provenance is malformed."
        raise DocumentRefusal(message) from error
    binding = decode(expected, values, label="style provenance", error=DocumentRefusal)
    if generated_name(purpose, binding) != name:
        message = "Generated style provenance is not canonical."
        raise DocumentRefusal(message)
    return binding


@dataclass(frozen=True, slots=True)
class StyleNormalization:
    references: tuple[str, ...]
    restore: Callable[[etree._Element, Mapping[str, str]], Mapping[str, str | None] | None]


def normalize_generated(root: etree._Element, *policies: StyleNormalization) -> etree._Element:
    """Copy once and restore only references authorized by verified purpose policies."""
    clone = copy.deepcopy(root)
    for source, target in zip(root.iter(), clone.iter(), strict=True):
        for policy in policies:
            restored = policy.restore(source, dict(target.attrib))
            if restored is None:
                continue
            for reference in policy.references:
                target.attrib.pop(reference, None)
            for reference, value in restored.items():
                if value is not None:
                    target.set(reference, value)
    return clone


class StyleResolver:
    """Resolve ODF style inheritance across the styles and content parts."""

    def __init__(self, content_tree: etree._ElementTree, styles_tree: etree._ElementTree) -> None:
        """Index the styles of live content and styles trees."""
        self.content_tree = content_tree
        self.styles_tree = styles_tree
        self._common: dict[tuple[str, str], list[etree._Element]] = {}
        self._automatic: dict[tuple[str, str], list[etree._Element]] = {}
        self._defaults: dict[str, list[etree._Element]] = {}
        self._scope_problems: list[str] = []
        self._index()

    @classmethod
    def for_document(cls, document: OdfDocument) -> StyleResolver:
        """Build a fresh lookup context over the document's current live trees."""
        return cls(*_trees(document))

    def _index(self) -> None:
        roots = {
            id(tree.getroot()): tree.getroot() for tree in (self.styles_tree, self.content_tree)
        }
        common_roots = {qn("office", name) for name in ("document", "document-styles")}
        if self.styles_tree.getroot().tag not in common_roots:
            self._scope_problems.append("Style styles part has an unsupported root.")
        for root in roots.values():
            if root.tag not in common_roots:
                continue
            containers = root.findall("office:styles", NS)
            if len(containers) > 1:
                self._scope_problems.append("Style common style scope is ambiguous.")
            for container in containers:
                for node in container.findall("style:default-style", NS):
                    self._defaults.setdefault(node.get(xml_names.STYLE_FAMILY, ""), []).append(node)
                for node in container.findall("style:style", NS):
                    self._add(self._common, node)
        self._index_automatic()

    def _index_automatic(self) -> None:
        automatic = self.content_tree.getroot().findall("office:automatic-styles", NS)
        if len(automatic) > 1:
            self._scope_problems.append("Style automatic style scope is ambiguous.")
        for container in automatic:
            for node in container.findall("style:style", NS):
                self._add(self._automatic, node)

    @staticmethod
    def _add(index: dict[tuple[str, str], list[etree._Element]], node: etree._Element) -> None:
        key = (node.get(xml_names.STYLE_FAMILY, ""), node.get(xml_names.STYLE_NAME, ""))
        if node not in index.setdefault(key, []):
            index[key].append(node)

    def register(self, family: str, style: etree._Element) -> None:
        """Index a newly adopted content automatic style without replacing authored nodes.

        Raises
        ------
        DocumentRefusal
            The registration contradicts the style's declared family.
        """
        if style.get(xml_names.STYLE_FAMILY) != family:
            msg = "Registered paragraph style has a contradictory family."
            raise DocumentRefusal(msg)
        self._add(self._automatic, style)

    def styles(self, family: str) -> list[etree._Element]:
        """Collect all legal common and content automatic definitions of a family.

        Returns
        -------
        list[etree._Element]
            Definitions retaining their distinct legal scopes.
        """
        self._require_scope()
        return [
            node
            for index in (self._common, self._automatic)
            for (kind, _name), nodes in index.items()
            if kind == family
            for node in nodes
        ]

    def resolve(
        self, family: str, name: str | None, *, common: bool = False
    ) -> etree._Element | None:
        """Resolve a unique style; absence remains available for derivation existence probes.

        Returns
        -------
        etree._Element | None
            The uniquely scoped definition, or None when absent.

        Raises
        ------
        DocumentRefusal
            The applicable scope is ambiguous or conditional.
        """
        self._require_scope()
        if not name:
            return None
        key = (family, name)
        nodes = (
            self._common.get(key, [])
            if common
            else self._automatic.get(key, []) or self._common.get(key, [])
        )
        if len(nodes) > 1:
            msg = f"Style {name!r} is ambiguous in its legal scope."
            raise DocumentRefusal(msg)
        if family in {"paragraph", "text"} and nodes and nodes[0].find("style:map", NS) is not None:
            msg = f"Conditional {family} style {name!r} cannot establish effective properties."
            raise DocumentRefusal(msg)
        return nodes[0] if nodes else None

    def _require_scope(self) -> None:
        if self._scope_problems:
            raise DocumentRefusal(" ".join(self._scope_problems))

    def parent_name(self, family: str, name: str | None) -> str | None:
        """Return a named style's parent if declared.

        Returns
        -------
        str | None
            The declared parent style name, or None.
        """
        style = self.resolve(family, name)
        return style.get(xml_names.STYLE_PARENT_STYLE_NAME) if style is not None else None

    def chain(self, family: str, name: str | None) -> list[etree._Element]:
        """Resolve scoped common parents, refusing missing references and cycles.

        Returns
        -------
        list[etree._Element]
            Ancestors followed by the requested style.

        Raises
        ------
        DocumentRefusal
            A reference is missing, ambiguous, conditional or cyclic.
        """
        if not name:
            return []
        style = self.resolve(family, name)
        if style is None:
            message = f"Style {name!r} is missing in its legal scope."
            raise DocumentRefusal(message)
        return self.chain_from(family, style)

    def chain_from(self, family: str, style: etree._Element) -> list[etree._Element]:
        """Resolve common parents of an already selected scoped definition."""
        chain = []
        seen = set()
        while True:
            if style in seen:
                message = "Style inheritance contains a cycle."
                raise DocumentRefusal(message)
            seen.add(style)
            chain.append(style)
            parent = style.get(xml_names.STYLE_PARENT_STYLE_NAME)
            if not parent:
                break
            found = self.resolve(family, parent, common=True)
            if found is None:
                message = f"Style {parent!r} is missing in its legal scope."
                raise DocumentRefusal(message)
            style = found
        chain.reverse()
        return chain

    def derive(
        self, family: str, base: etree._Element | None, *, purpose: str, binding: object
    ) -> GeneratedStyle:
        """Clone a selected base with one canonical purpose-tagged provenance encoding."""
        element = (
            copy.deepcopy(base)
            if base is not None
            else etree.Element(xml_names.STYLE_STYLE, nsmap=self.content_tree.getroot().nsmap)
        )
        name = generated_name(purpose, binding)
        element.set(xml_names.STYLE_NAME, name)
        element.set(xml_names.STYLE_FAMILY, family)
        return GeneratedStyle(name, element)

    def is_generated(
        self,
        existing: etree._Element,
        expected: GeneratedStyle,
        *,
        ignored: Mapping[str, Collection[str]] | None = None,
    ) -> bool:
        """Prove a content automatic definition against the declared derivation."""
        parent = existing.getparent()
        if (
            parent is None
            or parent.tag != xml_names.OFFICE_AUTOMATIC_STYLES
            or parent.getparent() is not self.content_tree.getroot()
        ):
            return False
        if existing.get(xml_names.STYLE_NAME) != expected.name:
            return False
        values = []
        for element in (existing, expected.element):
            clone = copy.deepcopy(element)
            for node in list(clone.iter()):
                if not isinstance(node.tag, str) or node.tag not in (ignored or {}):
                    continue
                for attribute in (ignored or {})[node.tag]:
                    node.attrib.pop(attribute, None)
                if (
                    not node.attrib
                    and not len(node)
                    and not node.text
                    and (parent := node.getparent()) is not None
                ):
                    parent.remove(node)
            values.append(_definition(clone))
        return values[0] == values[1]

    def effective(self, family: str, name: str | None, property_element: str) -> dict[str, str]:
        """Overlay default and inherited properties in precedence order.

        Returns
        -------
        dict[str, str]
            Default and inherited attributes overlaid in precedence order.

        Raises
        ------
        DocumentRefusal
            Applicable defaults or property targets are ambiguous.
        """
        props: dict[str, str] = {}
        self._require_scope()
        defaults = self._defaults.get(family, [])
        if len(defaults) > 1:
            msg = f"Default {family} style is ambiguous."
            raise DocumentRefusal(msg)
        for style in [*defaults, *self.chain(family, name)]:
            node = _properties(style, property_element)
            if node is not None:
                props.update(node.attrib)
        return props

    def effective_paragraph_properties(self, name: str | None) -> dict[str, str]:
        """Resolve inherited paragraph properties.

        Returns
        -------
        dict[str, str]
            Resolved paragraph attributes.
        """
        return self.effective("paragraph", name, "paragraph-properties")

    def effective_text_properties(self, name: str | None) -> dict[str, str]:
        """Resolve inherited text properties.

        Returns
        -------
        dict[str, str]
            Resolved text attributes.
        """
        return self.effective("paragraph", name, "text-properties")

    def spacing_signature(self, name: str | None) -> dict[str, str]:
        """Return effective spacing attributes using readable qualified names.

        Returns
        -------
        dict[str, str]
            Readable qualified spacing attributes and their values.
        """
        props = self.effective_paragraph_properties(name)
        return {display_attr(key): props[key] for key in SPACING_ATTRIBUTES if key in props}

    def own_spacing(self, name: str | None) -> dict[str, str]:
        """Return the spacing attributes a style declares itself, ignoring inheritance.

        Returns
        -------
        dict[str, str]
            Readable qualified spacing attributes declared directly on the style.
        """
        style = self.resolve("paragraph", name)
        props = _properties(style, "paragraph-properties") if style is not None else None
        if props is None:
            return {}
        return {
            display_attr(key): props.attrib[key]
            for key in SPACING_ATTRIBUTES
            if key in props.attrib
        }

    def has_break_semantics(self, name: str | None) -> bool:
        """Return whether a style carries page or master-page controls.

        Returns
        -------
        bool
            Whether effective properties declare a page break or master page.
        """
        props = self.effective_paragraph_properties(name)
        return any(
            key in props and props[key] not in {"auto", "none", ""} for key in BREAK_ATTRIBUTES
        ) or any(
            style.get(xml_names.STYLE_MASTER_PAGE_NAME) not in {None, "", "auto", "none"}
            for style in self.chain("paragraph", name)
        )


def styles_of(document: OdfDocument) -> StyleResolver:
    """Return the document's style catalog, built once over its live trees.

    Returns
    -------
    StyleResolver
        The catalog shared by every text operation on this document.
    """
    return document.derived("odf.styles", lambda: StyleResolver(*_trees(document)))


def _trees(document: OdfDocument) -> tuple[etree._ElementTree, etree._ElementTree]:
    content = document.tree(Part.CONTENT)
    if document.has(Part.STYLES):
        return content, document.tree(Part.STYLES)
    return content, etree.ElementTree(etree.Element(xml_names.OFFICE_DOCUMENT_STYLES))


def _properties(style: etree._Element, name: str) -> etree._Element | None:
    if style.find("style:map", NS) is not None:
        msg = "Conditional paragraph styles cannot establish effective properties."
        raise DocumentRefusal(msg)
    nodes = style.findall(qn("style", name))
    if len(nodes) > 1:
        msg = f"Style has ambiguous {name} targets."
        raise DocumentRefusal(msg)
    return nodes[0] if nodes else None


NO_STYLE = "(none)"


def derive_paragraph_style(
    catalog: StyleResolver,
    base_style_name: str | None,
    new_style_name: str,
    spacing: dict[str, str],
) -> etree._Element:
    """Build, without inserting it, a style equal to a base but with given spacing.

    Returns
    -------
    etree._Element
        A detached paragraph style named ``new_style_name``.

    """
    base = catalog.resolve("paragraph", base_style_name)
    generated = catalog.derive(
        "paragraph", base, purpose="spacing", binding=SpacingBinding(base_style_name)
    )
    if generated.name != new_style_name:
        message = "Spacing style name contradicts its declared provenance."
        raise DocumentRefusal(message)
    derived = generated.element
    set_spacing(derived, spacing)
    return derived


def is_generated_from(
    catalog: StyleResolver,
    existing: etree._Element,
    base_style_name: str | None,
    new_style_name: str,
) -> bool:
    """Whether a style is, apart from its spacing, exactly what we would derive.

    Only a style that lives among the automatic styles of the content part and equals the
    derivation of ``base_style_name`` in everything but spacing counts as generated by us;
    any other style of the same name belongs to someone else.

    Returns
    -------
    bool
        True when ``existing`` can be proven to be our own earlier output.

    """
    expected = derive_paragraph_style(catalog, base_style_name, new_style_name, {})
    return catalog.is_generated(
        existing,
        GeneratedStyle(new_style_name, expected),
        ignored={xml_names.STYLE_PARAGRAPH_PROPERTIES: SPACING_ATTRIBUTES},
    )


def adopt_style(catalog: StyleResolver, style: etree._Element) -> Allowance:
    """Insert a derived style among the content part's automatic styles and index it.

    Raises
    ------
    DocumentRefusal
        The style does not declare its family.

    """
    family = style.get(xml_names.STYLE_FAMILY)
    if not family:
        message = "An adopted style must declare its family."
        raise DocumentRefusal(message)
    auto_styles = catalog.content_tree.find("office:automatic-styles", NS)
    created_container = auto_styles is None
    if auto_styles is None:
        root = catalog.content_tree.getroot()
        auto_styles = etree.Element(xml_names.OFFICE_AUTOMATIC_STYLES)
        body = root.find("office:body", NS)
        insert_at = root.index(body) if body is not None else len(root)
        root.insert(insert_at, auto_styles)
    auto_styles.append(style)
    catalog.register(family, style)
    permissions = (Created.of(Part.CONTENT, style, style_name=style.get(xml_names.STYLE_NAME)),)
    containers = (Container(Part.CONTENT, auto_styles),) if created_container else ()
    return Allowance((*permissions, *containers))


def set_spacing(style: etree._Element, spacing: dict[str, str]) -> Allowance:
    """Replace the spacing attributes a style declares itself."""
    props = style.find(xml_names.STYLE_PARAGRAPH_PROPERTIES)
    created = props is None
    if props is None:
        props = etree.Element(xml_names.STYLE_PARAGRAPH_PROPERTIES)
        text_props = style.find(xml_names.STYLE_TEXT_PROPERTIES)
        position = style.index(text_props) if text_props is not None else 0
        style.insert(position, props)
    for key in SPACING_ATTRIBUTES:
        props.attrib.pop(key, None)
    for display_name, value in spacing.items():
        key = attr_from_display(display_name)
        if key in SPACING_ATTRIBUTES:
            props.set(key, value)
    permissions = (Attributes(Part.CONTENT, props, frozenset(SPACING_ATTRIBUTES)),)
    containers = (Container(Part.CONTENT, props),) if created else ()
    return Allowance((*permissions, *containers))


def derived_style_name(base: str) -> str:
    """Name the derived style that carries normalized spacing for a base style.

    The digest of the full base name keeps two bases that sanitise to the same text apart
    and keeps the name out of the way of styles an author is likely to choose.

    Returns
    -------
    str
        A deterministic style name containing only letters, digits and underscores.

    """
    return generated_name("spacing", SpacingBinding(None if base == NO_STYLE else base))


def display_attr(qname: str) -> str:
    """Render a Clark-notation attribute name with its namespace prefix.

    Returns
    -------
    str
        The prefixed name, or the input when its namespace is unknown.

    """
    for prefix, uri in NS.items():
        marker = f"{{{uri}}}"
        if qname.startswith(marker):
            return f"{prefix}:{qname[len(marker) :]}"
    return qname


def attr_from_display(name: str) -> str:
    """Parse a prefixed attribute name into Clark notation.

    Returns
    -------
    str
        The Clark-notation name, or the input when its prefix is unknown.

    """
    if ":" not in name:
        return name
    prefix, local = name.split(":", 1)
    if prefix not in NS:
        return name
    return qn(prefix, local)
