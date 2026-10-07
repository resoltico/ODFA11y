# SPDX-License-Identifier: MPL-2.0
"""Styles for ODF accessibility workflows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from .namespaces import NS, qn
from .style_properties import attr_from_display, display_attr, find_paragraphs_by_style
from .xpath import select_elements

if TYPE_CHECKING:
    from .package import OdtPackage

__all__ = ["ParagraphStyleUsage", "StyleCatalog", "find_paragraphs_by_style"]

SPACING_ATTRIBUTES = (
    qn("fo", "margin-top"),
    qn("fo", "margin-bottom"),
    qn("fo", "line-height"),
    qn("fo", "line-height-at-least"),
    qn("style", "contextual-spacing"),
)

BREAK_ATTRIBUTES = (
    qn("fo", "break-before"),
    qn("fo", "break-after"),
    qn("style", "master-page-name"),
)


@dataclass(slots=True, frozen=True)
class ParagraphStyleUsage:
    """Summarize effective spacing and use of a paragraph style."""

    style_name: str
    count: int
    spacing: dict[str, str]
    parent: str | None


class StyleCatalog:
    """Resolve ODF style inheritance across ``styles.xml`` and ``content.xml``."""

    def __init__(self, package: OdtPackage) -> None:
        """Load and index the document resources."""
        self.package = package
        self.content_tree = package.parse_xml("content.xml")
        self.styles_tree = package.parse_xml("styles.xml")
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

    def clone_paragraph_style_with_spacing(
        self,
        *,
        base_style_name: str | None,
        new_style_name: str,
        spacing: dict[str, str],
    ) -> etree._Element:
        """Create a distinct style with the requested spacing properties.

        Returns
        -------
        etree._Element
            The inserted style element.

        """
        auto_styles = self.content_tree.find("office:automatic-styles", NS)
        if auto_styles is None:
            root = self.content_tree.getroot()
            auto_styles = etree.Element(qn("office", "automatic-styles"))
            body = root.find("office:body", NS)
            insert_at = root.index(body) if body is not None else len(root)
            root.insert(insert_at, auto_styles)

        base = self.style("paragraph", base_style_name)
        if base is not None:
            clone = etree.fromstring(etree.tostring(base))
            clone.set(qn("style", "name"), new_style_name)
            clone.set(qn("style", "family"), "paragraph")
        else:
            clone = etree.Element(qn("style", "style"))
            clone.set(qn("style", "name"), new_style_name)
            clone.set(qn("style", "family"), "paragraph")
            if base_style_name:
                clone.set(qn("style", "parent-style-name"), base_style_name)

        pprops = clone.find(qn("style", "paragraph-properties"))
        if pprops is None:
            pprops = etree.SubElement(clone, qn("style", "paragraph-properties"))

        for key in SPACING_ATTRIBUTES:
            pprops.attrib.pop(key, None)
        for display_name, value in spacing.items():
            key = attr_from_display(display_name)
            if key in SPACING_ATTRIBUTES:
                pprops.set(key, value)

        # Avoid duplicate style names if called repeatedly in one run.
        for node in select_elements(auto_styles, "./style:style"):
            if node.get(qn("style", "name")) == new_style_name:
                auto_styles.remove(node)
        auto_styles.append(clone)
        self._styles["paragraph", new_style_name] = clone
        return clone

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

    def commit_content(self) -> None:
        """Save the edited content tree back into the in-memory package."""
        self.package.write_xml("content.xml", self.content_tree)
