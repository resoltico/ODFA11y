# SPDX-License-Identifier: MPL-2.0
"""Create an explicitly requested standard optional metadata part without replacing data."""

from lxml import etree

from odfa11y.errors import DocumentRefusal
from odfa11y.odf import names as xml_names
from odfa11y.odf.detect import declared_version
from odfa11y.odf.names import NS
from odfa11y.odf.schema import SUPPORTED_VERSIONS
from odfa11y.odf.storage import Part
from odfa11y.odf.xpath import select_elements
lazy from odfa11y.odf.document import OdfDocument


def ensure_metadata_part(document: OdfDocument) -> None:
    """Create missing package metadata and its manifest entry after complete preflight.

    Flat storage already exposes its one tree as the metadata part. The caller edits the
    metadata tree after this function; no requested value is inferred here.

    Raises
    ------
    DocumentRefusal
        Creation lacks a declared supported version, a storage slot or a consistent manifest.

    """
    if document.has(Part.META):
        return
    version = declared_version(document)
    name = document.storage.member_for(Part.META)
    if version not in SUPPORTED_VERSIONS or name is None:
        msg = (
            "Creating metadata requires a declared supported ODF version and metadata storage slot."
        )
        raise DocumentRefusal(msg)
    manifest = document.tree(Part.MANIFEST)
    entries = [
        node
        for node in select_elements(manifest, "//manifest:file-entry")
        if node.get(xml_names.MANIFEST_FULL_PATH) == name
    ]
    if len(entries) > 1 or (
        entries and entries[0].get(xml_names.MANIFEST_MEDIA_TYPE) != "text/xml"
    ):
        msg = "The metadata manifest declaration is duplicate or has a conflicting media type."
        raise DocumentRefusal(msg)
    root = etree.Element(
        xml_names.OFFICE_DOCUMENT_META,
        nsmap={prefix: NS[prefix] for prefix in ("office", "meta", "dc")},
    )
    root.set(xml_names.OFFICE_VERSION, version)
    etree.SubElement(root, xml_names.OFFICE_META)
    if not entries:
        parent = document.tree(Part.MANIFEST).getroot()
        entry = etree.SubElement(parent, xml_names.MANIFEST_FILE_ENTRY)
        entry.set(xml_names.MANIFEST_FULL_PATH, name)
        entry.set(xml_names.MANIFEST_MEDIA_TYPE, "text/xml")
    document.storage.write_member(
        name, etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    )
