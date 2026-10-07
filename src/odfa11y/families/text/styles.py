# SPDX-License-Identifier: MPL-2.0
"""Resolve paragraph style inheritance and derive styles with changed spacing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, Part, qn, select_elements

from .style_properties import BREAK_ATTRIBUTES, SPACING_ATTRIBUTES, display_attr

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

__all__ = ["ParagraphStyleUsage", "StyleCatalog", "catalog_of"]


@dataclass(slots=True, frozen=True)
class ParagraphStyleUsage:
    """Summarize effective spacing and use of a paragraph style."""

    style_name: str
    count: int
    spacing: dict[str, str]
    parent: str | None


class StyleCatalog:
    """Resolve ODF style inheritance across the styles and content parts."""

    def __init__(self, content_tree: etree._ElementTree, styles_tree: etree._ElementTree) -> None:
        """Index the styles of live content and styles trees."""
        self.content_tree = content_tree
        self.styles_tree = styles_tree
        self._styles: dict[tuple[str, str], etree._Element] = {}
        self._defaults: dict[str, etree._Element] = {}
        self._index()

    def _index(self) -> None:
        for tree in (self.styles_tree, self.content_tree):
            for default in select_elements(tree, "//style:default-style"):
                family = default.get(qn("style", "family"))
                if family:
                    self._defaults[family] = default
            for style in select_elements(tree, "//style:style"):
                name = style.get(qn("style", "name"))
                family = style.get(qn("style", "family"))
                if name and family:
                    self._styles[family, name] = style

    def register(self, family: str, style: etree._Element) -> None:
        """Index a style that was added to the live tree."""
        self._styles[family, style.get(qn("style", "name")) or ""] = style

    def style(self, family: str, name: str | None) -> etree._Element | None:
        """Look up a style by family and name.

        Returns
        -------
        etree._Element | None
            The matching style, or None when absent.

        """
        if not name:
            return None
        return self._styles.get((family, name))

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
        """Resolve ancestors in order while stopping inheritance cycles.

        Returns
        -------
        list[etree._Element]
            Ancestors followed by the requested style, without repeated cyclic entries.

        """
        chain: list[etree._Element] = []
        seen: set[str] = set()
        current = name
        while current and current not in seen:
            seen.add(current)
            style = self.style(family, current)
            if style is None:
                break
            chain.append(style)
            current = style.get(qn("style", "parent-style-name"))
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

        """
        props: dict[str, str] = {}
        default = self._defaults.get(family)
        if default is not None:
            node = default.find(qn("style", property_element))
            if node is not None:
                props.update(node.attrib)
        for style in self.inheritance_chain(family, name):
            node = style.find(qn("style", property_element))
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
        props = style.find("style:paragraph-properties", NS) if style is not None else None
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

    def paragraph_usage(self) -> list[ParagraphStyleUsage]:
        """Summarize style usage and effective paragraph spacing.

        Returns
        -------
        list[ParagraphStyleUsage]
            Style usage counts with effective spacing and parent names.

        """
        counts: Counter[str] = Counter()
        for p in select_elements(self.content_tree, "//text:p | //text:h"):
            name = p.get(qn("text", "style-name")) or "(none)"
            counts[name] += 1
        rows: list[ParagraphStyleUsage] = []
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            style_name = None if name == "(none)" else name
            rows.append(
                ParagraphStyleUsage(
                    style_name=name,
                    count=count,
                    spacing=self.spacing_signature(style_name),
                    parent=self.parent_name("paragraph", style_name),
                )
            )
        return rows


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
