# SPDX-License-Identifier: MPL-2.0
"""Set document title, description and language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.families import adapter_for
from odfa11y.odf import NS, Part, qn

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

LANGUAGE_TAG_RE = re.compile(r"(?:[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*|x(?:-[A-Za-z0-9]{1,8})+)")


@dataclass(frozen=True, slots=True)
class SetMetadata(Operation):
    """Set title, description and language; ``None`` leaves a field untouched.

    The language is written to the document metadata and, where the document's family keeps
    a default language in its styles, to that style as well.
    """

    title: str | None = None
    description: str | None = None
    language: str | None = None
    name: ClassVar[str] = "set_metadata"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        outcomes = []
        blank = [
            key
            for key, value in (("title", self.title), ("description", self.description))
            if value is not None and not value.strip()
        ]
        if blank:
            message = f"Document {' and '.join(blank)} must not be blank."
            return (Outcome(self.name, Status.FAILED, message, key=blank[0]),)
        for key, tag, value in (
            ("title", qn("dc", "title"), self.title),
            ("description", qn("dc", "description"), self.description),
        ):
            if value is not None:
                outcomes.append(self._text(document, key, tag, value.strip()))
        if self.language is not None:
            outcomes.append(self._language(document, self.language.strip()))
        return tuple(outcomes)

    def _text(self, document: OdfDocument, key: str, tag: str, value: str) -> Outcome:
        node = _meta_node(document, tag)
        if node is not None and (node.text or "") == value:
            return Outcome(self.name, Status.UNCHANGED, f"Document {key} already set.", key=key)
        _ensure_meta_node(document, tag).text = value
        return Outcome(self.name, Status.APPLIED, f"Set document {key}.", key=key, count=1)

    def _language(self, document: OdfDocument, tag: str) -> Outcome:
        tag = tag.replace("_", "-")  # accept the POSIX spelling of a BCP 47 tag
        if not LANGUAGE_TAG_RE.fullmatch(tag):
            return Outcome(
                self.name, Status.FAILED, f"Invalid language tag: {tag!r}", key="language"
            )
        adapter = adapter_for(document.kind)
        node = _meta_node(document, qn("dc", "language"))
        meta_changed = node is None or (node.text or "") != tag
        if meta_changed:
            _ensure_meta_node(document, qn("dc", "language")).text = tag
        style_changed = adapter.set_default_language(document, tag)
        if not (meta_changed or style_changed):
            return Outcome(self.name, Status.UNCHANGED, "Language already set.", key="language")
        return Outcome(
            self.name, Status.APPLIED, f"Set language to {tag}.", key="language", count=1
        )


def _meta_node(document: OdfDocument, tag: str) -> etree._Element | None:
    if not document.has(Part.META):
        return None
    return document.tree(Part.META).find(f"office:meta/{_prefixed(tag)}", NS)


def _ensure_meta_node(document: OdfDocument, tag: str) -> etree._Element:
    meta = document.edit(Part.META)
    office_meta = meta.find("office:meta", NS)
    if office_meta is None:
        office_meta = etree.Element(qn("office", "meta"))
        meta.getroot().insert(0, office_meta)  # first child: the schema orders meta before body
    node = office_meta.find(_prefixed(tag), NS)
    if node is None:
        node = etree.SubElement(office_meta, tag)
    return node


def _prefixed(clark: str) -> str:
    namespace, local = clark[1:].split("}")
    prefix = next(prefix for prefix, uri in NS.items() if uri == namespace)
    return f"{prefix}:{local}"
