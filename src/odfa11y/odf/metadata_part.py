# SPDX-License-Identifier: MPL-2.0
"""Create an explicitly requested standard optional metadata part without replacing data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.errors import RemediationError

from .detect import declared_version
from .namespaces import NS, qn
from .schema import SUPPORTED_VERSIONS
from .storage import Part
from .xpath import select_elements

if TYPE_CHECKING:
    from .document import OdfDocument


def ensure_metadata_part(document: OdfDocument) -> None:
    """Create missing package metadata and its manifest entry after complete preflight.

    Flat storage already exposes its one tree as the metadata part. The caller edits the
    metadata tree after this function; no requested value is inferred here.

    Raises
    ------
    RemediationError
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
        raise RemediationError(msg)
    manifest = document.tree(Part.MANIFEST)
    entries = [
        node
        for node in select_elements(manifest, "//manifest:file-entry")
        if node.get(qn("manifest", "full-path")) == name
    ]
    if len(entries) > 1 or (entries and entries[0].get(qn("manifest", "media-type")) != "text/xml"):
        msg = "The metadata manifest declaration is duplicate or has a conflicting media type."
        raise RemediationError(msg)
    root = etree.Element(
        qn("office", "document-meta"),
        nsmap={prefix: NS[prefix] for prefix in ("office", "meta", "dc")},
    )
    root.set(qn("office", "version"), version)
    etree.SubElement(root, qn("office", "meta"))
    if not entries:
        parent = document.edit(Part.MANIFEST).getroot()
        entry = etree.SubElement(parent, qn("manifest", "file-entry"))
        entry.set(qn("manifest", "full-path"), name)
        entry.set(qn("manifest", "media-type"), "text/xml")
    document.storage.write_member(
        name, etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    )
