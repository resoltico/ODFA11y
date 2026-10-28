# SPDX-License-Identifier: MPL-2.0
"""Resolve scoped paragraph styles and derive verifiable spacing styles."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.content import protected_xml
from odfa11y.errors import RemediationError
from odfa11y.odf import NS, Part, qn

from .style_properties import BREAK_ATTRIBUTES, SPACING_ATTRIBUTES, attr_from_display, display_attr

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


class StyleCatalog:
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

    def _index(self) -> None:
        roots = {
            id(tree.getroot()): tree.getroot() for tree in (self.styles_tree, self.content_tree)
        }
        common_roots = {qn("office", name) for name in ("document", "document-styles")}
        if self.styles_tree.getroot().tag not in common_roots:
            self._scope_problems.append("Paragraph styles part has an unsupported root.")
        for root in roots.values():
            if root.tag not in common_roots:
                continue
            containers = root.findall("office:styles", NS)
            if len(containers) > 1:
                self._scope_problems.append("Paragraph common style scope is ambiguous.")
            for container in containers:
                for node in container.findall("style:default-style", NS):
                    self._defaults.setdefault(node.get(qn("style", "family"), ""), []).append(node)
                for node in container.findall("style:style", NS):
                    self._add(self._common, node)
        self._index_automatic()

    def _index_automatic(self) -> None:
        automatic = self.content_tree.getroot().findall("office:automatic-styles", NS)
        if len(automatic) > 1:
            self._scope_problems.append("Paragraph automatic style scope is ambiguous.")
        for container in automatic:
            for node in container.findall("style:style", NS):
                self._add(self._automatic, node)

    @staticmethod
    def _add(index: dict[tuple[str, str], list[etree._Element]], node: etree._Element) -> None:
        key = (node.get(qn("style", "family"), ""), node.get(qn("style", "name"), ""))
        if node not in index.setdefault(key, []):
            index[key].append(node)

    def register(self, family: str, style: etree._Element) -> None:
        """Index a newly adopted content automatic style without replacing authored nodes.

        Raises
        ------
        RemediationError
            The registration contradicts the style's declared family.
        """
        if style.get(qn("style", "family")) != family:
            msg = "Registered paragraph style has a contradictory family."
            raise RemediationError(msg)
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

    def style(
        self, family: str, name: str | None, *, common: bool = False
    ) -> etree._Element | None:
        """Resolve a unique style; absence remains available for derivation existence probes.

        Returns
        -------
        etree._Element | None
            The uniquely scoped definition, or None when absent.

        Raises
        ------
        RemediationError
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
            msg = f"Paragraph style {name!r} is ambiguous in its legal scope."
            raise RemediationError(msg)
        if nodes and nodes[0].find("style:map", NS) is not None:
            msg = f"Conditional paragraph style {name!r} cannot establish effective properties."
            raise RemediationError(msg)
        return nodes[0] if nodes else None

    def _require_scope(self) -> None:
        if self._scope_problems:
            raise RemediationError(" ".join(self._scope_problems))

    def parent_name(self, family: str, name: str | None) -> str | None:
        """Return a named style's parent if declared.

        Returns
        -------
        str | None
            The declared parent style name, or None.
        """
        style = self.style(family, name)
        return style.get(qn("style", "parent-style-name")) if style is not None else None

    def inheritance_chain(self, family: str, name: str | None) -> list[etree._Element]:
        """Resolve scoped common parents, refusing missing references and cycles.

        Returns
        -------
        list[etree._Element]
            Ancestors followed by the requested style.

        Raises
        ------
        RemediationError
            A reference is missing, ambiguous, conditional or cyclic.
        """
        chain: list[etree._Element] = []
        seen: set[etree._Element] = set()
        current = name
        common = False
        while current:
            style = self.style(family, current, common=common)
            if style is None:
                msg = f"Paragraph style {current!r} is missing in its legal scope."
                raise RemediationError(msg)
            if style in seen:
                msg = f"Paragraph style inheritance contains a cycle at {current!r}."
                raise RemediationError(msg)
            seen.add(style)
            chain.append(style)
            current = style.get(qn("style", "parent-style-name"))
            common = True
        chain.reverse()
        return chain

    def effective_properties(
        self, family: str, name: str | None, property_element: str
    ) -> dict[str, str]:
        """Overlay default and inherited properties in precedence order.

        Returns
        -------
        dict[str, str]
            Default and inherited attributes overlaid in precedence order.

        Raises
        ------
        RemediationError
            Applicable defaults or property targets are ambiguous.
        """
        props: dict[str, str] = {}
        self._require_scope()
        defaults = self._defaults.get(family, [])
        if len(defaults) > 1:
            msg = f"Default {family} style is ambiguous."
            raise RemediationError(msg)
        for style in [*defaults, *self.inheritance_chain(family, name)]:
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
        return self.effective_properties("paragraph", name, "paragraph-properties")

    def effective_text_properties(self, name: str | None) -> dict[str, str]:
        """Resolve inherited text properties.

        Returns
        -------
        dict[str, str]
            Resolved text attributes.
        """
        return self.effective_properties("paragraph", name, "text-properties")

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
        style = self.style("paragraph", name)
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
            style.get(qn("style", "master-page-name")) not in {None, "", "auto", "none"}
            for style in self.inheritance_chain("paragraph", name)
        )


def catalog_of(document: OdfDocument) -> StyleCatalog:
    """Return the document's style catalog, built once over its live trees.

    Returns
    -------
    StyleCatalog
        The catalog shared by every text operation on this document.
    """
    return document.derived("text.style_catalog", lambda: StyleCatalog(*_trees(document)))


def _trees(document: OdfDocument) -> tuple[etree._ElementTree, etree._ElementTree]:
    content = document.tree(Part.CONTENT)
    if document.has(Part.STYLES):
        return content, document.tree(Part.STYLES)
    return content, etree.ElementTree(etree.Element(qn("office", "document-styles")))


def _properties(style: etree._Element, name: str) -> etree._Element | None:
    if style.find("style:map", NS) is not None:
        msg = "Conditional paragraph styles cannot establish effective properties."
        raise RemediationError(msg)
    nodes = style.findall(qn("style", name))
    if len(nodes) > 1:
        msg = f"Paragraph style has ambiguous {name} targets."
        raise RemediationError(msg)
    return nodes[0] if nodes else None


NO_STYLE = "(none)"


SAFE_NAME_LENGTH = 32


NAME_DIGEST_LENGTH = 8


def derive_paragraph_style(
    catalog: StyleCatalog,
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
    base = catalog.style("paragraph", base_style_name)
    if base is not None:
        derived = copy.deepcopy(base)
    else:
        derived = etree.Element(qn("style", "style"), nsmap=catalog.content_tree.getroot().nsmap)
        if base_style_name:
            derived.set(qn("style", "parent-style-name"), base_style_name)
    derived.set(qn("style", "name"), new_style_name)
    derived.set(qn("style", "family"), "paragraph")
    set_spacing(derived, spacing)
    return derived


def is_generated_from(
    catalog: StyleCatalog,
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
    parent = existing.getparent()
    if (
        parent is None
        or parent.tag != qn("office", "automatic-styles")
        or parent.getparent() is not catalog.content_tree.getroot()
    ):
        return False
    if parent.getroottree().getroot() is not catalog.content_tree.getroot():
        return False
    expected = derive_paragraph_style(catalog, base_style_name, new_style_name, {})
    return _style_fingerprint(existing) == _style_fingerprint(expected)


def adopt_style(catalog: StyleCatalog, style: etree._Element) -> None:
    """Insert a derived style among the content part's automatic styles and index it.

    Raises
    ------
    RemediationError
        The style does not declare its family.

    """
    family = style.get(qn("style", "family"))
    if not family:
        message = "An adopted style must declare its family."
        raise RemediationError(message)
    auto_styles = catalog.content_tree.find("office:automatic-styles", NS)
    if auto_styles is None:
        root = catalog.content_tree.getroot()
        auto_styles = etree.Element(qn("office", "automatic-styles"))
        body = root.find("office:body", NS)
        insert_at = root.index(body) if body is not None else len(root)
        root.insert(insert_at, auto_styles)
    auto_styles.append(style)
    catalog.register(family, style)


def set_spacing(style: etree._Element, spacing: dict[str, str]) -> None:
    """Replace the spacing attributes a style declares itself."""
    props = style.find(qn("style", "paragraph-properties"))
    if props is None:
        props = etree.Element(qn("style", "paragraph-properties"))
        text_props = style.find(qn("style", "text-properties"))
        position = style.index(text_props) if text_props is not None else 0
        style.insert(position, props)
    for key in SPACING_ATTRIBUTES:
        props.attrib.pop(key, None)
    for display_name, value in spacing.items():
        key = attr_from_display(display_name)
        if key in SPACING_ATTRIBUTES:
            props.set(key, value)


def _style_fingerprint(style: etree._Element) -> str:
    """Fingerprint a style outside spacing, retaining referenced namespace bindings.

    Returns
    -------
    str
        Protected XML digest of a copy that carries no spacing.

    """
    clone = copy.deepcopy(style)
    props = clone.find(qn("style", "paragraph-properties"))
    if props is not None:
        for key in SPACING_ATTRIBUTES:
            props.attrib.pop(key, None)
    return protected_xml(clone)


def derived_style_name(base: str) -> str:
    """Name the derived style that carries normalized spacing for a base style.

    The digest of the full base name keeps two bases that sanitise to the same text apart
    and keeps the name out of the way of styles an author is likely to choose.

    Returns
    -------
    str
        A deterministic style name containing only letters, digits and underscores.

    """
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_")[:SAFE_NAME_LENGTH] or "Body"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:NAME_DIGEST_LENGTH]
    return f"A11ySpacing_{safe}_{digest}"
