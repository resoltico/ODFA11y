# SPDX-License-Identifier: MPL-2.0
"""Audit package for ODF accessibility workflows."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, ODT_MIMETYPE, REQUIRED_XML, qn
from odfa11y.report import Severity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from odfa11y.odf import OdtPackage
    from odfa11y.report import AuditReport


def audit_package(package: OdtPackage, report: AuditReport) -> None:
    """Report package-level defects such as duplicate or missing required members."""
    names = list(package.member_names())
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        report.add(
            "PKG006",
            Severity.ERROR,
            "ODT package contains duplicate ZIP member names.",
            details={"duplicates": duplicates},
        )
    if "mimetype" not in package.members:
        report.add("PKG001", Severity.ERROR, "ODT package has no mimetype member.", fixable=False)
    else:
        value = package.read("mimetype")
        try:
            decoded = value.decode("ascii")
        except UnicodeDecodeError:
            decoded = "<non-ASCII>"
        if decoded != ODT_MIMETYPE:
            report.add(
                "PKG002",
                Severity.ERROR,
                f"mimetype is {decoded!r}; expected {ODT_MIMETYPE!r}.",
                location="mimetype",
            )
        info = package.members["mimetype"].info
        if not names or names[0] != "mimetype":
            report.add(
                "PKG003",
                Severity.ERROR,
                "mimetype is not the first ZIP member.",
                location="mimetype",
                fixable=True,
            )
        if info.compress_type != zipfile.ZIP_STORED:
            report.add(
                "PKG004",
                Severity.ERROR,
                "mimetype is compressed; ODF requires it to be stored uncompressed.",
                location="mimetype",
                fixable=True,
            )

    for name in REQUIRED_XML:
        if not package.has(name):
            report.add(
                "PKG005", Severity.ERROR, f"Required ODT member is missing: {name}", location=name
            )


def audit_versions(
    trees: dict[str, etree._ElementTree], report: AuditReport, target_version: str
) -> None:
    """Report ODF version declarations that differ from the target version."""
    for name in ("content.xml", "styles.xml", "meta.xml", "settings.xml"):
        if name not in trees:
            continue
        root = trees[name].getroot()
        value = root.get(qn("office", "version"))
        if value != target_version:
            report.add(
                "ODF001",
                Severity.ERROR,
                f"{name} declares ODF version {value!r}; expected {target_version!r}.",
                location=name,
                fixable=True,
            )
    root = trees["META-INF/manifest.xml"].getroot()
    value = root.get(qn("manifest", "version"))
    if value != target_version:
        report.add(
            "ODF001",
            Severity.ERROR,
            f"META-INF/manifest.xml declares ODF version {value!r}; expected {target_version!r}.",
            location="META-INF/manifest.xml",
            fixable=True,
        )

    root_entries = root.xpath("./manifest:file-entry[@manifest:full-path='/']", namespaces=NS)
    if not root_entries:
        report.add(
            "ODF002",
            Severity.ERROR,
            "Manifest has no root file-entry for '/'.",
            location="META-INF/manifest.xml",
            fixable=False,
        )
    else:
        entry = root_entries[0]
        entry_version = entry.get(qn("manifest", "version"))
        media_type = entry.get(qn("manifest", "media-type"))
        if entry_version != target_version:
            report.add(
                "ODF003",
                Severity.ERROR,
                (
                    f"Manifest root file-entry declares version "
                    f"{entry_version!r}; expected {target_version!r}."
                ),
                location="META-INF/manifest.xml",
                fixable=True,
            )
        if media_type != ODT_MIMETYPE:
            report.add(
                "ODF004",
                Severity.ERROR,
                f"Manifest root media type is {media_type!r}; expected {ODT_MIMETYPE!r}.",
                location="META-INF/manifest.xml",
                fixable=True,
            )


def validate_relaxng(
    trees: dict[str, etree._ElementTree],
    *,
    schema: Path,
    member_names: Iterable[str],
    report: AuditReport,
    rule_id: str,
) -> None:
    """Report Relax NG schema violations for the supplied validators."""
    if not schema.is_file():
        report.add(
            rule_id, Severity.ERROR, f"Relax NG schema not found: {schema}", location=str(schema)
        )
        return
    try:
        schema_tree = etree.parse(
            str(schema), parser=etree.XMLParser(resolve_entities=False, no_network=True)
        )
        validator = etree.RelaxNG(schema_tree)
    except (OSError, etree.Error, ValueError) as exc:
        report.add(
            rule_id, Severity.ERROR, f"Could not load Relax NG schema: {exc}", location=str(schema)
        )
        return
    for name in member_names:
        tree = trees[name]
        if not validator.validate(tree):
            report.add(
                rule_id,
                Severity.ERROR,
                f"{name} does not validate against {schema.name}.",
                location=name,
                details={"errors": [str(e) for e in validator.error_log]},
            )
