# SPDX-License-Identifier: MPL-2.0
"""Operation-specific protected XML facts for supported Writer edits."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import TYPE_CHECKING

from odfa11y.content import (
    SHAPE_TAGS,
    GraphicIdentity,
    document_links,
    link_location,
    normalized_role_attributes,
    protected_xml,
)
from odfa11y.errors import XmlParseError
from odfa11y.odf import Part, qn

from .contexts import context_location, text_nodes
from .derived_styles import is_generated_from
from .graphics import SetGraphicAlternatives, SetLinkDescriptions
from .headings import SetHeadingLevels, heading_location
from .linkify import LinkifyAddresses
from .prose import address_wrapper_scope
from .protection_metadata import normalize_metadata
from .protection_structure import normalize_headers, unwrap_address
from .remove_spacers import RemoveEmptySpacers
from .spacers import spacer_candidates
from .spacing import NO_STYLE, NormalizeSpacing, derived_style_name
from .styles import catalog_of
from .tables import MarkTableHeaders

if TYPE_CHECKING:
    from collections.abc import Callable

    from lxml import etree

    from odfa11y.adapter import Operation
    from odfa11y.odf import OdfDocument


class ProtectedEdit:
    """Capture immutable protected facts and normalize only this operation's effects."""

    def __init__(self, document: OdfDocument, operation: Operation) -> None:
        self.document = document
        self.operation = operation
        self.creating_metadata = not document.has(Part.META)
        self.allowed: dict[etree._Element, set[str]] = {}
        self.descriptions: dict[etree._Element, set[str]] = {}
        self.spacers: set[etree._Element] = set()
        self.tables: set[etree._Element] = set()
        self.spacing: dict[str, str] = {}
        self.spacing_targets: set[etree._Element] = set()
        self.links = set(document.tree(Part.CONTENT).iter(qn("text", "a")))
        self.roles: set[etree._Element] = set()
        self._establish()
        self.before = self._facts()

    def _establish(self) -> None:
        tree = self.document.tree(Part.CONTENT)
        op = self.operation
        if type(op) is SetHeadingLevels:
            for index, node in enumerate(text_nodes(tree, qn("text", "h"), main_only=True), 1):
                if heading_location(node, index).path in op.entries:
                    self.allowed[node] = {qn("text", "outline-level")}
        elif type(op) is RemoveEmptySpacers:
            self.spacers = {
                node
                for node in spacer_candidates(tree)
                if not catalog_of(self.document).has_break_semantics(
                    node.get(qn("text", "style-name"))
                )
            }
        elif type(op) is MarkTableHeaders:
            self.tables = {
                node
                for index, node in enumerate(text_nodes(tree, qn("table", "table")), 1)
                if node.get(qn("table", "name")) in op.entries
                or context_location(node, "table", index, node.get(qn("table", "name"))).path
                in op.entries
            }
        elif type(op) is NormalizeSpacing:
            for base in op.target_styles:
                self.spacing[derived_style_name(base)] = base
            tags = (qn("text", "p"), qn("text", "h")) if op.include_headings else (qn("text", "p"),)
            self.spacing_targets = {
                node
                for node in text_nodes(tree, *tags, main_only=True)
                if (node.get(qn("text", "style-name")) or NO_STYLE)
                in {*op.target_styles, *self.spacing}
            }
        elif type(op) is SetGraphicAlternatives:
            self._alternatives(op)
        elif type(op) is SetLinkDescriptions:
            self._links(op)

    def _alternatives(self, operation: SetGraphicAlternatives) -> None:
        frames = text_nodes(self.document.tree(Part.CONTENT), *SHAPE_TAGS)
        identity = GraphicIdentity(self.document, frames)
        for selector, entry in operation.entries.items():
            matches = identity.matching(selector)
            for field, tag in (
                (entry.title, qn("svg", "title")),
                (entry.description, qn("svg", "desc")),
            ):
                if field is not None:
                    for match in matches:
                        self.descriptions.setdefault(match, set()).add(tag)
            if entry.decorative is not None:
                self.roles.update(matches)

    def _links(self, operation: SetLinkDescriptions) -> None:
        for index, node in enumerate(document_links(self.document), 1):
            if link_location(node, index).path in operation.entries:
                self.allowed[node] = {qn("office", "title")}

    def intact(self) -> bool:
        """Whether all protected facts remain identical after the operation.

        Returns
        -------
        bool
            True only when differences fit the established edit contract.

        """
        return self.before == self._facts()

    def _facts(self) -> tuple[str, ...]:
        facts = []
        seen = set()
        for part in Part:
            name = self.document.member_name(part)
            if name is None or name in seen:
                continue
            seen.add(name)
            try:
                fact = self._tree_facts(self.document.tree(part).getroot())
            except XmlParseError:
                fact = (
                    "unparsed:"
                    + name
                    + ":"
                    + hashlib.sha256(self.document.storage.read(name)).hexdigest()
                )
            if fact is not None:
                facts.append(fact)
        return tuple(facts)

    def _tree_facts(self, root: etree._Element) -> str | None:
        clone = deepcopy(root)
        generated: set[str] = set()
        for source, target in list(zip(root.iter(), clone.iter(), strict=True)):
            generated.update(self._node(source, target))
        self._spacing(clone)
        for style in list(clone.iter(qn("style", "style"))):
            if (
                style.get(qn("style", "name")) in generated
                and (parent := style.getparent()) is not None
            ):
                parent.remove(style)
        normalize_metadata(clone, self.operation, creating_metadata=self.creating_metadata)
        for container in list(clone.iter(qn("office", "automatic-styles"))):
            if (
                not len(container)
                and not container.attrib
                and (parent := container.getparent()) is not None
            ):
                parent.remove(container)
        if (
            clone.tag == qn("office", "document-meta")
            and not len(clone)
            and set(clone.attrib) <= {qn("office", "version")}
        ):
            return None
        return protected_xml(clone)

    def _node(self, source: etree._Element, target: etree._Element) -> set[str]:
        for attr in self.allowed.get(source, ()):
            target.attrib.pop(attr, None)
        if source in self.descriptions:
            for tag in self.descriptions[source]:
                child = target.find(tag)
                if child is not None:
                    target.remove(child)
        if source in self.spacers and (parent := target.getparent()) is not None:
            parent.remove(target)
        if source in self.spacing_targets:
            self._spacing_reference(source, target)
        if source in self.tables:
            normalize_headers(target)
        if (
            type(self.operation) is LinkifyAddresses
            and source.tag == qn("text", "a")
            and source not in self.links
            and address_wrapper_scope(source)
        ):
            unwrap_address(source, target)
        return self._role(source, target) if source in self.roles else set()

    def _role(self, source: etree._Element, target: etree._Element) -> set[str]:
        original = normalized_role_attributes(self.document, source)
        generated = set()
        for ns in ("draw", "presentation"):
            for name in ("style-name", "class-names"):
                attr = qn(ns, name)
                value = source.get(attr, "")
                if value != original.get(attr, ""):
                    generated.update(
                        token
                        for token in value.split()
                        if token not in original.get(attr, "").split()
                    )
                target.attrib.pop(attr, None)
        target.attrib.update(original)
        return generated

    def _spacing(self, root: etree._Element) -> None:
        if not self.spacing:
            return
        catalog = catalog_of(self.document)
        proven = set()
        for name, base in self.spacing.items():
            style = catalog.style("paragraph", name)
            if style is not None and is_generated_from(
                catalog, style, None if base == NO_STYLE else base, name
            ):
                proven.add(name)
        for node in list(root.iter()):
            if (
                node.tag == qn("style", "style")
                and node.get(qn("style", "name")) in proven
                and (parent := node.getparent()) is not None
            ):
                parent.remove(node)

    def _spacing_reference(self, source: etree._Element, target: etree._Element) -> None:
        name = source.get(qn("text", "style-name"))
        if name not in self.spacing:
            return
        base = self.spacing[name]
        catalog = catalog_of(self.document)
        style = catalog.style("paragraph", name)
        if style is not None and is_generated_from(
            catalog, style, None if base == NO_STYLE else base, name
        ):
            if base == NO_STYLE:
                target.attrib.pop(qn("text", "style-name"), None)
            else:
                target.set(qn("text", "style-name"), base)


def protect_edit(document: OdfDocument, operation: Operation) -> Callable[[], bool]:
    """Bind the operation to independent protected XML facts before mutation.

    Returns
    -------
    Callable[[], bool]
        A check of the current document against the captured immutable facts.

    """
    return ProtectedEdit(document, operation).intact
