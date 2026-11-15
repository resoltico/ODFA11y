# SPDX-License-Identifier: MPL-2.0
"""Set document title, description and language."""

from lxml import etree

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import DocumentMetadataAnswer
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.families import require_spec
from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, Part, ensure_metadata_part
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


def _meta_node(document: OdfDocument, tag: str) -> etree._Element | None:
    if not document.has(Part.META):
        return None
    return document.tree(Part.META).find(f"office:meta/{_prefixed(tag)}", NS)


def _ensure_meta_node(document: OdfDocument, tag: str) -> etree._Element:
    ensure_metadata_part(document)
    meta = document.tree(Part.META)
    office_meta = meta.find("office:meta", NS)
    if office_meta is None:
        office_meta = etree.Element(xml_names.OFFICE_META)
        meta.getroot().insert(0, office_meta)  # first child: the schema orders meta before body
    node = office_meta.find(_prefixed(tag), NS)
    if node is None:
        node = etree.SubElement(office_meta, tag)
    return node


def _prefixed(clark: str) -> str:
    namespace, local = clark[1:].split("}")
    prefix = next(prefix for prefix, uri in NS.items() if uri == namespace)
    return f"{prefix}:{local}"


def edit_metadata(
    document: OdfDocument, decision: Decision[DocumentMetadataAnswer]
) -> tuple[Outcome, ...]:
    """Set supplied document metadata and the family's established default language."""
    answer = decision.answer
    adapter = require_spec(document.kind)
    language = normalize_language(answer.language) if answer.language is not None else None
    if language is not None and adapter.language is not None:
        try:
            adapter.language.read(document)
        except ValueError as error:
            raise DocumentRefusal(str(error)) from error
    outcomes = []
    for key, tag, value in (
        ("title", xml_names.DC_TITLE, answer.title),
        ("description", xml_names.DC_DESCRIPTION, answer.description),
    ):
        if value is None:
            continue
        clean_value = value.strip()
        node = _meta_node(document, tag)
        changed = node is None or (node.text or "") != clean_value
        if changed:
            _ensure_meta_node(document, tag).text = clean_value
        outcomes.append(
            Outcome(
                decision.kind.id,
                Status.APPLIED if changed else Status.UNCHANGED,
                f"Set document {key}." if changed else f"Document {key} already set.",
                target=key,
                count=int(changed),
            )
        )
    if language is not None:
        node = _meta_node(document, xml_names.DC_LANGUAGE)
        changed = node is None or (node.text or "") != language
        if changed:
            _ensure_meta_node(document, xml_names.DC_LANGUAGE).text = language
        changed = (
            adapter.language.write(document, language) if adapter.language is not None else False
        ) or changed
        outcomes.append(
            Outcome(
                decision.kind.id,
                Status.APPLIED if changed else Status.UNCHANGED,
                f"Set language to {language}." if changed else "Language already set.",
                target="language",
                count=int(changed),
            )
        )
    return tuple(outcomes)
