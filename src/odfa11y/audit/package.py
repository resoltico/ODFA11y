# SPDX-License-Identifier: MPL-2.0
"""Audit ZIP package structure, ODF version declarations and schema validity."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from odfa11y.errors import XmlParseError
from odfa11y.odf import (
    ODT_MIMETYPE,
    REQUIRED_XML,
    declared_version,
    is_unsafe_member_name,
    qn,
    select_elements,
    validate,
)
from odfa11y.report import rules

if TYPE_CHECKING:
    from odfa11y.odf import OdtDocument, OdtPackage
    from odfa11y.report import Report

MAX_REPORTED_VIOLATIONS = 20


def audit_package(package: OdtPackage, report: Report) -> None:
    """Report package-level defects such as duplicate or missing required members."""
    names = list(package.member_names())
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        report.add(
            rules.PKG006,
            "ODT package contains duplicate ZIP member names.",
            details={"duplicates": duplicates},
        )
    if "mimetype" not in package.members:
        report.add(rules.PKG001, "ODT package has no mimetype member.")
    else:
        value = package.read("mimetype")
        try:
            decoded = value.decode("ascii")
        except UnicodeDecodeError:
            decoded = "<non-ASCII>"
        if decoded != ODT_MIMETYPE:
            report.add(
                rules.PKG002,
                f"mimetype is {decoded!r}; expected {ODT_MIMETYPE!r}.",
                location="mimetype",
            )
        info = package.members["mimetype"].info
        if not names or names[0] != "mimetype":
            report.add(rules.PKG003, location="mimetype")
        if info.compress_type != zipfile.ZIP_STORED:
            report.add(
                rules.PKG004,
                "mimetype is compressed; ODF requires it to be stored uncompressed.",
                location="mimetype",
            )

    for name in REQUIRED_XML:
        if not package.has(name):
            report.add(rules.PKG005, f"Required ODT member is missing: {name}", location=name)
    unsafe = sorted(name for name in names if is_unsafe_member_name(name))
    if unsafe:
        report.add(rules.PKG007, details={"names": unsafe})


def audit_versions(document: OdtDocument, report: Report) -> None:
    """Report ODF version declarations that disagree across members or the manifest."""
    version = declared_version(document)
    members = [
        name
        for name in ("content.xml", "styles.xml", "meta.xml", "settings.xml")
        if document.has(name)
    ]
    declared = {}
    for name in members:
        try:
            declared[name] = document.tree(name).getroot().get(qn("office", "version"))
        except XmlParseError:
            continue  # reported as XML001 by the caller
    if version is None or len(set(declared.values())) > 1:
        report.add(
            rules.ODF001,
            "Package members declare different or missing ODF versions.",
            details={"versions": declared},
        )
    if version is not None:
        report.metadata["odf_version"] = version
    manifest_root = document.tree("META-INF/manifest.xml").getroot()
    manifest_version = manifest_root.get(qn("manifest", "version"))
    if manifest_version is not None and manifest_version != version:
        report.add(
            rules.ODF003,
            f"Manifest declares ODF version {manifest_version!r}; content declares {version!r}.",
            location="META-INF/manifest.xml",
        )
    root_entries = select_elements(manifest_root, "./manifest:file-entry[@manifest:full-path='/']")
    if not root_entries:
        report.add(rules.ODF002, location="META-INF/manifest.xml")
        return
    entry = root_entries[0]
    entry_version = entry.get(qn("manifest", "version"))
    if entry_version is not None and entry_version != version:
        report.add(
            rules.ODF003,
            (
                f"Manifest root file-entry declares version {entry_version!r}; "
                f"content declares {version!r}."
            ),
            location="META-INF/manifest.xml",
        )
    if entry.get(qn("manifest", "media-type")) != ODT_MIMETYPE:
        report.add(
            rules.ODF004,
            f"Manifest root media type is not {ODT_MIMETYPE!r}.",
            location="META-INF/manifest.xml",
        )


def audit_schema(document: OdtDocument, report: Report) -> None:
    """Report members that violate the bundled ODF schema for the declared version."""
    result = validate(document)
    report.metadata["schema_version"] = result.version
    if not result.available:
        report.add(
            rules.ODF905,
            f"No ODF schema is bundled for declared version {result.version!r}.",
        )
        return
    report.metadata["schema_violations"] = result.count
    for member, messages in result.violations.items():
        report.add(
            rules.ODF900,
            f"{member} does not validate against the ODF {result.version} schema.",
            location=member,
            details={
                "count": len(messages),
                "violations": list(messages[:MAX_REPORTED_VIOLATIONS]),
            },
        )
