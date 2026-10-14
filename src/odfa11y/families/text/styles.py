# SPDX-License-Identifier: MPL-2.0
"""Resolve paragraph style inheritance and derive styles with changed spacing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.errors import RemediationError
from odfa11y.odf import NS, Part, qn

from .style_properties import BREAK_ATTRIBUTES, SPACING_ATTRIBUTES, display_attr

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

__all__ = ["StyleCatalog", "catalog_of"]


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
