# SPDX-License-Identifier: MPL-2.0
"""Audit storage structure, the document kind and ODF version declarations."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, cast

from odfa11y.errors import XmlParseError
from odfa11y.odf import (
    Family,
    Part,
    declared_version,
    is_office_element,
    is_unsafe_member_name,
    qn,
    select_elements,
    validate,
)
from odfa11y.report import Location, rules

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument, PackageStorage
    from odfa11y.report import Report

MAX_REPORTED_VIOLATIONS = 20
MIMETYPE = "mimetype"
MIMETYPE_LOCATION = Location("package/mimetype", MIMETYPE)
OFFICE_ROOT_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.SETTINGS)


def storage_location(document: OdfDocument, part: Part) -> Location:
    """Locate a part for a finding about how it is stored.

    A flat document keeps every part in one file, so its findings name ``document``; a
    package's name the part and the member that holds it.

    Returns
    -------
    Location
        The logical location, with the package member where there is one.

    """
    if document.layout == "flat":
        return Location("document")
    return Location(part.value, document.member_name(part))


def audit_structure(document: OdfDocument, report: Report) -> bool:
    """Report storage-level defects of a package or a flat document.

    Returns
    -------
    bool
        False when the document lacks what any further audit needs.

    """
    if document.layout == "flat":
        return _audit_flat(document, report)
    return _audit_package(document, report)


def _audit_flat(document: OdfDocument, report: Report) -> bool:
    try:
        root = document.tree(Part.CONTENT).getroot()
    except XmlParseError as exc:
        report.add(rules.XML001, str(exc), location=storage_location(document, Part.CONTENT))
        return False
    if root.tag != qn("office", "document"):
        report.add(
            rules.ODF010,
            f"The root element is {root.tag!r}; a flat document's root is office:document.",
        )
        return False
    if document.detection.media_type is None:
        report.add(rules.PKG001, "The document has no office:mimetype attribute.")
    return True


def _audit_package(document: OdfDocument, report: Report) -> bool:
    package = cast("PackageStorage", document.storage)
    names = list(package.member_names())
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        report.add(
            rules.PKG006,
            "Package contains duplicate ZIP member names.",
            details={"duplicates": duplicates},
        )
    _audit_mimetype(package, names, report)
    unsafe = sorted(name for name in names if is_unsafe_member_name(name))
    if unsafe:
        report.add(rules.PKG007, details={"names": unsafe})
    usable = True
    for part in (Part.MANIFEST, Part.CONTENT):
        if not document.has(part):
            name = package.member_for(part)
            report.add(
                rules.PKG005,
                f"Required package member is missing: {name}",
                location=Location(part.value, name),
            )
            usable = False
    for part in (Part.STYLES, Part.META):
        if not document.has(part):
            name = package.member_for(part)
            report.add(
                rules.PKG002,
                f"Optional package member is missing: {name}",
                location=Location(part.value, name),
            )
    return usable


def _audit_mimetype(package: PackageStorage, names: list[str], report: Report) -> None:
    if MIMETYPE not in package.members:
        report.add(
            rules.PKG001,
            "Package has no mimetype member; tools cannot recognise its type without it.",
        )
        return
    info = package.members[MIMETYPE].info
    raw = package.read(MIMETYPE)
    if not raw.isascii() or raw != raw.strip():
        report.add(
            rules.PKG001,
            "mimetype is not exactly an ASCII media type (stray whitespace or non-ASCII bytes).",
            location=MIMETYPE_LOCATION,
        )
    if not names or names[0] != MIMETYPE:
        report.add(rules.PKG003, location=MIMETYPE_LOCATION)
    if info.compress_type != zipfile.ZIP_STORED:
        report.add(
            rules.PKG004,
            "mimetype is compressed; ODF requires it to be stored uncompressed.",
            location=MIMETYPE_LOCATION,
        )


def audit_kind(document: OdfDocument, report: Report) -> bool:
    """Report what the media type, body element and extension say about the document kind.

    Returns
    -------
    bool
        False when the media type is not an OpenDocument one, which ends the audit.

    """
    detection = document.detection
    kind = detection.kind
    report.metadata["layout"] = document.layout
    report.metadata["media_type"] = detection.media_type
    if kind is None:
        report.add(
            rules.ODF005,
            f"The media type {detection.media_type!r} is not an OpenDocument document type.",
            details={"media_type": detection.media_type, "declared_by": detection.declared_by},
        )
        return False
    report.metadata["document_kind"] = kind.name
    report.metadata["family"] = kind.family.value
    if (
        detection.manifest_media_type is not None
        and detection.media_type is not None
        and detection.manifest_media_type != detection.media_type
    ):
        report.add(
            rules.ODF004,
            f"The manifest declares {detection.manifest_media_type!r}; the document declares "
            f"{detection.media_type!r}.",
            location=storage_location(document, Part.MANIFEST),
        )
    if kind.body_element is not None and detection.body_element != kind.body_element:
        report.add(
            rules.ODF006,
            f"The body holds {detection.body_element!r}; a {kind.name} document holds "
            f"{kind.body_element!r}.",
            details={"body": detection.body_element, "expected": kind.body_element},
        )
    expected = _extensions(kind.extension, flat=document.layout == "flat")
    flat_variant = document.layout == "flat" and detection.extension.startswith(".fo")
    if detection.extension not in expected and not flat_variant:
        report.add(
            rules.ODF007,
            f"The file extension {detection.extension!r} does not match a {kind.name} document "
            f"({', '.join(sorted(expected))}).",
        )
    if kind.deprecated:
        report.add(rules.ODF008, f"The {kind.media_type} media type is deprecated.")
    _audit_content_root(document, kind.family, report)
    return True


def _audit_content_root(document: OdfDocument, family: Family, report: Report) -> None:
    if document.layout != "package" or family is Family.FORMULA or not document.has(Part.CONTENT):
        return
    try:
        root = document.tree(Part.CONTENT).getroot()
    except XmlParseError:
        return  # the XML audit reports it
    if root.tag != qn("office", "document-content"):
        report.add(
            rules.ODF011,
            f"The content root is {root.tag!r}; it must be office:document-content.",
            location=storage_location(document, Part.CONTENT),
        )


def _extensions(extension: str, *, flat: bool) -> set[str]:
    return {f".f{extension[1:]}", ".xml"} if flat else {extension}  # flat: or any ".fo*"


def audit_versions(document: OdfDocument, report: Report) -> None:
    """Report ODF version declarations that disagree across members or the manifest."""
    version = declared_version(document)
    declared = {}
    for part in OFFICE_ROOT_PARTS:
        name = document.member_name(part)
        if name is None or name in declared:
            continue
        try:
            root = document.tree(part).getroot()
        except XmlParseError:
            continue  # reported as XML001 by the caller
        if is_office_element(root):
            declared[name] = root.get(qn("office", "version"))
    if version is None or len(set(declared.values())) > 1:
        report.add(
            rules.ODF001,
            "Package members declare different or missing ODF versions.",
            details={"versions": declared},
        )
    if version is not None:
        report.metadata["odf_version"] = version
    if document.has(Part.MANIFEST):
        _audit_manifest(document, version, report)


def _audit_manifest(document: OdfDocument, version: str | None, report: Report) -> None:
    manifest_root = document.tree(Part.MANIFEST).getroot()
    manifest_version = manifest_root.get(qn("manifest", "version"))
    if manifest_version is not None and manifest_version != version:
        report.add(
            rules.ODF003,
            f"Manifest declares ODF version {manifest_version!r}; content declares {version!r}.",
            location=storage_location(document, Part.MANIFEST),
        )
    root_entries = select_elements(manifest_root, "./manifest:file-entry[@manifest:full-path='/']")
    if not root_entries:
        report.add(rules.ODF002, location=storage_location(document, Part.MANIFEST))
        return
    entry_version = root_entries[0].get(qn("manifest", "version"))
    if entry_version is not None and entry_version != version:
        report.add(
            rules.ODF003,
            (
                f"Manifest root file-entry declares version {entry_version!r}; "
                f"content declares {version!r}."
            ),
            location=storage_location(document, Part.MANIFEST),
        )


def audit_schema(document: OdfDocument, report: Report) -> None:
    """Report members that violate the bundled ODF schema for the declared version."""
    result = validate(document)
    report.metadata["schema_version"] = result.version
    if not result.available:
        reason = (
            f"No ODF schema is bundled for declared version {result.version!r}."
            if result.version
            else "The document declares no ODF version, so no schema applies."
        )
        report.add(rules.ODF905, reason)
        return
    report.metadata["schema_violations"] = result.count
    report.metadata["schema_violations_unlocated"] = result.unlocated
    for member, messages in result.messages().items():
        location = storage_location(document, _part_of(document, member))
        report.add(
            rules.ODF900,
            f"The {location.path} does not validate against the ODF {result.version} schema.",
            location=location,
            details={
                "count": len(messages),
                "violations": list(messages[:MAX_REPORTED_VIOLATIONS]),
            },
        )


def _part_of(document: OdfDocument, member: str) -> Part:
    return next(part for part in Part if document.member_name(part) == member)
