# SPDX-License-Identifier: MPL-2.0
"""Identify what kind of document a storage holds and which ODF version it declares."""

from dataclasses import dataclass

lazy from lxml import etree

from odfa11y.errors import PackageError
from odfa11y.odf import names as xml_names
from odfa11y.odf.kinds import OASIS_PREFIX, kind_for_media_type
from odfa11y.odf.names import NS, is_office_element
from odfa11y.odf.storage import Layout, Part
from odfa11y.odf.xpath import select_elements
lazy from odfa11y.odf.document import OdfDocument
lazy from odfa11y.odf.kinds import DocumentKind

MIMETYPE_MEMBER = xml_names.MIMETYPE_MEMBER


@dataclass(frozen=True, slots=True)
class Detection:
    """What the document says it is, where it said so, and what its body actually is."""

    kind: DocumentKind | None
    layout: Layout
    odf_version: str | None
    media_type: str | None
    declared_by: str
    manifest_media_type: str | None
    body_element: str | None
    extension: str


def detect(document: OdfDocument) -> Detection:
    """Read the declared media type, the manifest's media type and the body element.

    The media type is the ``mimetype`` file of a package or the ``office:mimetype``
    attribute of a flat document, falling back to the manifest's root entry. The file
    extension is corroboration only and never selects the kind.

    Returns
    -------
    Detection
        The kind (None when the media type is not an OpenDocument one) and its evidence.

    """
    declared, declared_by = _declared_media_type(document)
    manifest = _manifest_media_type(document)
    if declared is None and manifest is not None:
        declared, declared_by = manifest, "manifest"
    return Detection(
        kind=kind_for_media_type(declared),
        layout=document.layout,
        odf_version=declared_version(document),
        media_type=declared,
        declared_by=declared_by if declared is not None else "none",
        manifest_media_type=manifest,
        body_element=_body_element(document),
        extension=document.storage.source.suffix.lower(),
    )


def is_odf_container(document: OdfDocument) -> bool:
    """Recognize ODF declarations or roots independently of supported media types."""
    if (document.detection.media_type or "").startswith(OASIS_PREFIX):
        return True
    if not document.has(Part.CONTENT):
        return False
    return document.tree(Part.CONTENT).getroot().tag in {
        xml_names.OFFICE_DOCUMENT,
        xml_names.OFFICE_DOCUMENT_CONTENT,
    }


def declared_version(document: OdfDocument) -> str | None:
    """Read the ODF version the document declares.

    The content root's ``office:version`` is authoritative; documents whose content root
    is not an office document root (a formula) use the manifest's declaration.

    Returns
    -------
    str | None
        The declared version, or None when absent or unreadable.

    """
    root = _root(document, Part.CONTENT)
    if root is not None and is_office_element(root):
        return root.get(xml_names.OFFICE_VERSION)
    manifest = _root(document, Part.MANIFEST)
    if manifest is None:
        return None
    entry = _root_entry(manifest)
    return (entry.get(xml_names.MANIFEST_VERSION) if entry is not None else None) or manifest.get(
        xml_names.MANIFEST_VERSION
    )


def _declared_media_type(document: OdfDocument) -> tuple[str | None, str]:
    storage = document.storage
    if storage.layout == "flat":
        root = _root(document, Part.CONTENT)
        value = root.get(xml_names.OFFICE_MIMETYPE) if root is not None else None
        return value, "office:mimetype"
    if storage.has(MIMETYPE_MEMBER):
        try:
            return storage.read(MIMETYPE_MEMBER).decode("ascii").strip() or None, MIMETYPE_MEMBER
        except UnicodeDecodeError:
            return None, MIMETYPE_MEMBER
    return None, "none"


def _manifest_media_type(document: OdfDocument) -> str | None:
    manifest = _root(document, Part.MANIFEST)
    entry = _root_entry(manifest) if manifest is not None else None
    return entry.get(xml_names.MANIFEST_MEDIA_TYPE) if entry is not None else None


def _root_entry(manifest: etree._Element) -> etree._Element | None:
    entries = select_elements(manifest, "./manifest:file-entry[@manifest:full-path='/']")
    return entries[0] if entries else None


def _body_element(document: OdfDocument) -> str | None:
    root = _root(document, Part.CONTENT)
    body = root.find("office:body", NS) if root is not None else None
    if body is None:
        return None
    for child in body:
        if isinstance(child.tag, str) and is_office_element(child):
            return "office:" + child.tag.rpartition("}")[2]
    return None


def _root(document: OdfDocument, part: Part) -> etree._Element | None:
    if not document.has(part):
        return None
    try:
        return document.tree(part).getroot()
    except PackageError:
        return None
