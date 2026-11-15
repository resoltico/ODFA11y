# SPDX-License-Identifier: MPL-2.0
"""Protect Writer content and normalize only the metadata each operation may change."""

import hashlib
from copy import deepcopy
lazy from collections.abc import Callable

lazy from lxml import etree

from odfa11y.concepts import (
    normalized_role_attributes,
    protected_xml,
    repeated,
)
from odfa11y.contracts import record_dict
from odfa11y.decisions.answers import DocumentMetadataAnswer, OdfVersionAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.errors import XmlParseError
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.language.operations import prepare_language
from odfa11y.families.text.language.styles import STYLE_NAME
from odfa11y.families.text.links.prose import address_wrapper_scope
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.families.text.spacing.candidates import spacer_candidates
from odfa11y.families.text.styles.catalogue import (
    NO_STYLE,
    catalog_of,
    derived_style_name,
    is_generated_from,
)
from odfa11y.odf import NS, Part, qn
from odfa11y.odf import names as xml_names
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument


class ProtectedEdit:
    """Capture immutable protected facts and normalize only this operation's effects."""

    def __init__(self, document: OdfDocument, operation: Decision) -> None:
        self.document = document
        self.operation = operation
        self.creating_metadata = not document.has(Part.META)
        self.allowed: dict[etree._Element, set[str]] = {}
        self.descriptions: dict[etree._Element, set[str]] = {}
        self.spacers: set[etree._Element] = set()
        self.tables: set[etree._Element] = set()
        self.spacing: dict[str, str] = {}
        self.spacing_targets: set[etree._Element] = set()
        self.links = set(document.tree(Part.CONTENT).iter(xml_names.TEXT_A))
        self.roles: set[etree._Element] = set()
        self.language_targets: dict[etree._Element, tuple[str | None, str]] = {}
        self.language_styles: dict[str, str] = {}
        self._establish()
        self.before = self._facts()

    def _establish(self) -> None:
        tree = self.document.tree(Part.CONTENT)
        op = self.operation
        if op.kind.id == "language.target":
            self._establish_language(op)
        elif op.kind.id == "heading.level":
            self.allowed[resolved_node(self.document, op)] = {xml_names.TEXT_OUTLINE_LEVEL}
        elif op.kind.id == "text.remove_spacers" and op.answer.enabled:
            self.spacers = {
                node
                for node in spacer_candidates(tree)
                if not catalog_of(self.document).has_break_semantics(
                    node.get(xml_names.TEXT_STYLE_NAME)
                )
            }
        elif op.kind.id == "table.headers":
            self.tables = {resolved_node(self.document, op)}
        elif op.kind.id == "text.spacing":
            self._establish_spacing(op)
        elif op.kind.id == "graphic.alternative":
            self._alternatives(op)
        elif op.kind.id == "link.description":
            self.allowed[resolved_node(self.document, op)] = {xml_names.OFFICE_TITLE}

    def _establish_spacing(self, operation: Decision) -> None:
        tree = self.document.tree(Part.CONTENT)
        answer = operation.answer
        for base in answer.target_styles:
            self.spacing[derived_style_name(base)] = base
        tags = (
            (xml_names.TEXT_P, xml_names.TEXT_H) if answer.include_headings else (xml_names.TEXT_P,)
        )
        self.spacing_targets = {
            node
            for node in text_nodes(tree, *tags, main_only=True)
            if (node.get(xml_names.TEXT_STYLE_NAME) or NO_STYLE)
            in {*answer.target_styles, *self.spacing}
        }

    def _establish_language(self, operation: Decision) -> None:
        item = prepare_language(self.document, operation)
        if item.changed:
            self.language_targets[item.node] = (item.node.get(STYLE_NAME), item.binding.name)
            self.language_styles[item.binding.name] = protected_xml(item.style)

    def _alternatives(self, operation: Decision) -> None:
        node = resolved_node(self.document, operation)
        answer = operation.answer
        for value, tag in (
            (answer.title, xml_names.SVG_TITLE),
            (answer.description, xml_names.SVG_DESC),
        ):
            if value is not None:
                self.descriptions.setdefault(node, set()).add(tag)
        if answer.decorative is not None:
            self.roles.add(node)

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
        for style in list(clone.iter(xml_names.STYLE_STYLE)):
            if (
                style.get(xml_names.STYLE_NAME) in generated
                and (parent := style.getparent()) is not None
            ):
                parent.remove(style)
        for style in list(clone.iter(xml_names.STYLE_STYLE)):
            name = style.get(xml_names.STYLE_NAME)
            if (
                name in self.language_styles
                and protected_xml(style) == self.language_styles[name]
                and (parent := style.getparent()) is not None
            ):
                parent.remove(style)
        normalize_metadata(clone, self.operation, creating_metadata=self.creating_metadata)
        for container in list(clone.iter(xml_names.OFFICE_AUTOMATIC_STYLES)):
            if (
                not len(container)
                and not container.attrib
                and (parent := container.getparent()) is not None
            ):
                parent.remove(container)
        if (
            clone.tag == xml_names.OFFICE_DOCUMENT_META
            and not len(clone)
            and set(clone.attrib) <= {xml_names.OFFICE_VERSION}
        ):
            return None
        return protected_xml(clone)

    def _node(self, source: etree._Element, target: etree._Element) -> set[str]:
        self._language_reference(source, target)
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
            self.operation.kind.id == "text.linkify_addresses"
            and self.operation.answer.enabled
            and source.tag == xml_names.TEXT_A
            and source not in self.links
            and address_wrapper_scope(source)
        ):
            unwrap_address(source, target)
        return self._role(source, target) if source in self.roles else set()

    def _language_reference(self, source: etree._Element, target: etree._Element) -> None:
        if source in self.language_targets:
            before, desired = self.language_targets[source]
            if source.get(STYLE_NAME) == desired:
                target.attrib.pop(STYLE_NAME, None)
                if before is not None:
                    target.set(STYLE_NAME, before)

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
                node.tag == xml_names.STYLE_STYLE
                and node.get(xml_names.STYLE_NAME) in proven
                and (parent := node.getparent()) is not None
            ):
                parent.remove(node)

    def _spacing_reference(self, source: etree._Element, target: etree._Element) -> None:
        name = source.get(xml_names.TEXT_STYLE_NAME)
        if name not in self.spacing:
            return
        base = self.spacing[name]
        catalog = catalog_of(self.document)
        style = catalog.style("paragraph", name)
        if style is not None and is_generated_from(
            catalog, style, None if base == NO_STYLE else base, name
        ):
            if base == NO_STYLE:
                target.attrib.pop(xml_names.TEXT_STYLE_NAME, None)
            else:
                target.set(xml_names.TEXT_STYLE_NAME, base)


def protect_edit(document: OdfDocument, operation: Decision) -> Callable[[], bool]:
    """Bind the operation to independent protected XML facts before mutation.

    Returns
    -------
    Callable[[], bool]
        A check of the current document against the captured immutable facts.

    """
    return ProtectedEdit(document, operation).intact


LANGUAGE_ATTRIBUTES = frozenset(
    [qn("fo", name) for name in ("language", "country", "script")]
    + [
        qn("style", name)
        for name in (
            "rfc-language-tag",
            "rfc-language-tag-asian",
            "rfc-language-tag-complex",
            "language-asian",
            "country-asian",
            "script-asian",
            "language-complex",
            "country-complex",
            "script-complex",
        )
    ]
)


def normalize_metadata(
    root: etree._Element, operation: Decision, *, creating_metadata: bool
) -> None:
    """Normalize supported metadata effects without masking unrelated styles."""
    if isinstance(operation.answer, OdfVersionAnswer):
        _version(root)
    if not isinstance(operation.answer, DocumentMetadataAnswer):
        return
    if creating_metadata:
        _metadata_entry(root)
    parameters = record_dict(operation.answer)
    fields = {
        qn("dc", key)
        for key in ("title", "description", "language")
        if parameters.get(key) is not None
    }
    for meta in root.findall("office:meta", NS):
        for tag in fields:
            node = meta.find(tag)
            if node is not None:
                meta.remove(node)
        if not len(meta) and not meta.attrib and (parent := meta.getparent()) is not None:
            parent.remove(meta)
    if parameters.get("language") is not None:
        _language_defaults(root)


def _version(root: etree._Element) -> None:
    root.attrib.pop(xml_names.OFFICE_VERSION, None)
    if root.tag == xml_names.MANIFEST_MANIFEST:
        root.attrib.pop(xml_names.MANIFEST_VERSION, None)
        for entry in root.findall("manifest:file-entry", NS):
            if entry.get(xml_names.MANIFEST_FULL_PATH) == "/":
                entry.attrib.pop(xml_names.MANIFEST_VERSION, None)


def _language_defaults(root: etree._Element) -> None:
    for default in root.findall("office:styles/style:default-style", NS):
        if default.get(xml_names.STYLE_FAMILY) != "paragraph":
            continue
        _default_properties(default)
    for styles in root.findall("office:styles", NS):
        if not len(styles) and not styles.attrib and (parent := styles.getparent()) is not None:
            parent.remove(styles)


def _metadata_entry(root: etree._Element) -> None:
    if root.tag != xml_names.MANIFEST_MANIFEST:
        return
    for entry in list(root):
        if (
            entry.tag == xml_names.MANIFEST_FILE_ENTRY
            and dict(entry.attrib)
            == {xml_names.MANIFEST_FULL_PATH: "meta.xml", xml_names.MANIFEST_MEDIA_TYPE: "text/xml"}
            and not len(entry)
        ):
            root.remove(entry)


def _default_properties(default: etree._Element) -> None:
    for props in list(default.findall("style:text-properties", NS)):
        for attr in list(props.attrib):
            if attr in LANGUAGE_ATTRIBUTES:
                props.attrib.pop(attr)
        if not props.attrib and not len(props):
            default.remove(props)
    if (
        len(default) == 0
        and dict(default.attrib) == {xml_names.STYLE_FAMILY: "paragraph"}
        and (parent := default.getparent()) is not None
    ):
        parent.remove(default)


def unwrap_address(source: etree._Element, target: etree._Element) -> None:
    """Remove only a newly created exact address wrapper in a protected copy."""
    token = source.text or ""
    match = URI_RE.fullmatch(token)
    if not match or len(source):
        return
    address, punctuation = split_trailing_punctuation(token)
    expected = f"mailto:{address}" if match.group("email") else address
    if punctuation or dict(source.attrib) != {
        xml_names.XLINK_TYPE: "simple",
        xml_names.XLINK_HREF: expected,
    }:
        return
    parent = target.getparent()
    if parent is None:
        return
    value = token + (target.tail or "")
    previous = target.getprevious()
    if previous is None:
        parent.text = (parent.text or "") + value
    else:
        previous.tail = (previous.tail or "") + value
    parent.remove(target)


def normalize_headers(table: etree._Element) -> None:
    """Ignore this table's header wrappers and coalesce proven identical repeated runs."""
    for node in list(
        table.iter(xml_names.TABLE_TABLE_HEADER_ROWS, xml_names.TABLE_TABLE_HEADER_COLUMNS)
    ):
        parent = node.getparent()
        owner = next(node.iterancestors(xml_names.TABLE_TABLE), None)
        if parent is None or owner is not table:
            continue
        position = parent.index(node)
        for offset, child in enumerate(list(node)):
            parent.insert(position + offset, child)
        parent.remove(node)
    for parent in table.iter():
        owner = (
            parent
            if parent.tag == xml_names.TABLE_TABLE
            else next(parent.iterancestors(xml_names.TABLE_TABLE), None)
        )
        if owner is not table:
            continue
        _coalesce_declarations(parent)


def _coalesce_declarations(parent: etree._Element) -> None:
    previous = None
    for child in list(parent):
        if child.tag not in {xml_names.TABLE_TABLE_ROW, xml_names.TABLE_TABLE_COLUMN}:
            previous = None
            continue
        repeat = qn(
            "table",
            "number-rows-repeated"
            if child.tag == xml_names.TABLE_TABLE_ROW
            else "number-columns-repeated",
        )
        count = str(repeated(child, repeat.rsplit("}", 1)[-1]))
        child.attrib.pop(repeat, None)
        if child.tail and not child.tail.strip():
            child.tail = None
        if previous is not None:
            old_count = previous.attrib.pop(repeat, "1")
            equal = protected_xml(previous) == protected_xml(child)
            previous.set(repeat, old_count)
            if equal:
                previous.set(repeat, str(int(old_count) + int(count)))
                parent.remove(child)
                continue
        child.set(repeat, count)
        previous = child
