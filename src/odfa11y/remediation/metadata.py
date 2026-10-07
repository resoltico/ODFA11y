# SPDX-License-Identifier: MPL-2.0
"""Set document title, description and language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.odf import NS, qn, select_elements

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from odfa11y.odf import OdtDocument

LANGUAGE_TAG_RE = re.compile(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*")


@dataclass(frozen=True, slots=True)
class SetMetadata(Operation):
    """Set title, description and language; ``None`` leaves a field untouched."""

    title: str | None = None
    description: str | None = None
    language: str | None = None
    name: ClassVar[str] = "set_metadata"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        outcomes = []
        for key, tag, value in (
            ("title", qn("dc", "title"), self.title),
            ("description", qn("dc", "description"), self.description),
        ):
            if value is not None:
                outcomes.append(self._text(document, key, tag, value.strip()))
        if self.language is not None:
            outcomes.append(self._language(document, self.language.strip()))
        return tuple(outcomes)

    def _text(self, document: OdtDocument, key: str, tag: str, value: str) -> Outcome:
        node = document.tree("meta.xml").find(f"office:meta/{_prefixed(tag)}", NS)
        if node is not None and (node.text or "") == value:
            return Outcome(self.name, Status.UNCHANGED, f"Document {key} already set.", key=key)
        meta = document.edit("meta.xml")
        office_meta = meta.find("office:meta", NS)
        if office_meta is None:
            office_meta = etree.SubElement(meta.getroot(), qn("office", "meta"))
        node = office_meta.find(_prefixed(tag), NS)
        if node is None:
            node = etree.SubElement(office_meta, tag)
        node.text = value
        return Outcome(self.name, Status.APPLIED, f"Set document {key}.", key=key, count=1)

    def _language(self, document: OdtDocument, tag: str) -> Outcome:
        if not LANGUAGE_TAG_RE.fullmatch(tag):
            return Outcome(
                self.name, Status.FAILED, f"Invalid language tag: {tag!r}", key="language"
            )
        language, country = _split_language(tag)
        meta_node = document.tree("meta.xml").find("office:meta/dc:language", NS)
        style_props = _default_text_properties(document.tree("styles.xml"))
        current = (
            (style_props.get(qn("fo", "language")), style_props.get(qn("fo", "country")))
            if style_props is not None
            else (None, None)
        )
        if (
            meta_node is not None
            and (meta_node.text or "") == tag
            and current == (language, country)
        ):
            return Outcome(self.name, Status.UNCHANGED, "Language already set.", key="language")
        meta = document.edit("meta.xml")
        office_meta = meta.find("office:meta", NS)
        if office_meta is None:
            office_meta = etree.SubElement(meta.getroot(), qn("office", "meta"))
        node = office_meta.find("dc:language", NS)
        if node is None:
            node = etree.SubElement(office_meta, qn("dc", "language"))
        node.text = tag
        props = _ensure_default_text_properties(document.edit("styles.xml"))
        props.set(qn("fo", "language"), language)
        if country:
            props.set(qn("fo", "country"), country)
        else:
            props.attrib.pop(qn("fo", "country"), None)
        return Outcome(
            self.name, Status.APPLIED, f"Set language to {tag}.", key="language", count=1
        )


def _prefixed(clark: str) -> str:
    namespace, local = clark[1:].split("}")
    prefix = next(prefix for prefix, uri in NS.items() if uri == namespace)
    return f"{prefix}:{local}"


def _default_text_properties(styles: etree._ElementTree) -> etree._Element | None:
    nodes = select_elements(
        styles,
        "//office:styles/style:default-style[@style:family='paragraph']/style:text-properties",
    )
    return nodes[0] if nodes else None


def _ensure_default_text_properties(styles: etree._ElementTree) -> etree._Element:
    existing = _default_text_properties(styles)
    if existing is not None:
        return existing
    container = styles.find("office:styles", NS)
    if container is None:
        container = etree.SubElement(styles.getroot(), qn("office", "styles"))
    defaults = select_elements(container, "./style:default-style[@style:family='paragraph']")
    if defaults:
        default = defaults[0]
    else:
        default = etree.Element(qn("style", "default-style"))
        default.set(qn("style", "family"), "paragraph")
        container.insert(0, default)
    return etree.SubElement(default, qn("style", "text-properties"))


def _split_language(tag: str) -> tuple[str, str | None]:
    parts = tag.replace("_", "-").split("-")
    country = next((part.upper() for part in parts[1:] if re.fullmatch(r"[A-Za-z]{2}", part)), None)
    return parts[0].lower(), country
