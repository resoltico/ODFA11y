# SPDX-License-Identifier: MPL-2.0
"""Audit for ODF accessibility workflows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .audit_metadata import _audit_metadata
from .audit_package import _audit_package, _audit_versions, _validate_relaxng
from .audit_semantics import (
    _audit_headings,
    _audit_images,
    _audit_tables,
)
from .document_text import _element_text, _is_empty_paragraph
from .links import URI_RE, split_trailing_punctuation
from .models import AuditReport, Severity
from .namespaces import NS, qn
from .odt_package import REQUIRED_XML, OdtPackage
from .styles import StyleCatalog

if TYPE_CHECKING:
    from lxml import etree


def audit_odt(
    source: str | Path,
    *,
    target_version: str = "1.4",
    schema: str | Path | None = None,
    manifest_schema: str | Path | None = None,
) -> AuditReport:
    """Audit package structure, document semantics and optional schemas.

    Returns
    -------
    AuditReport
        Package and document findings, plus discovered metadata.

    """
    source = Path(source)
    report = AuditReport(subject=str(source))

    try:
        package = OdtPackage(source)
    except (OSError, ValueError, RuntimeError) as exc:
        report.add("PKG000", Severity.ERROR, str(exc), location=str(source))
        return report

    _audit_package(package, report)
    if any(not package.has(name) for name in REQUIRED_XML):
        return report

    trees: dict[str, etree._ElementTree] = {}
    xml_members = list(REQUIRED_XML)
    if package.has("settings.xml"):
        xml_members.append("settings.xml")
    for name in xml_members:
        try:
            trees[name] = package.parse_xml(name)
        except (ValueError, KeyError) as exc:
            report.add("XML001", Severity.ERROR, str(exc), location=name)

    if any(name not in trees for name in REQUIRED_XML):
        return report

    _audit_versions(trees, report, target_version)
    _audit_metadata(trees["meta.xml"], trees["styles.xml"], report)
    _audit_headings(trees["content.xml"], report)
    _audit_images(trees["content.xml"], report)
    _audit_tables(trees["content.xml"], report)
    _audit_links(trees["content.xml"], report)
    _audit_empty_spacers(trees["content.xml"], package, report)
    _audit_notes(trees["content.xml"], report)
    _audit_blinking(trees, report)
    _audit_style_summary(package, report)

    if schema:
        schema_members = ["content.xml", "styles.xml", "meta.xml"]
        if "settings.xml" in trees:
            schema_members.append("settings.xml")
        _validate_relaxng(
            trees,
            schema=Path(schema),
            member_names=tuple(schema_members),
            report=report,
            rule_id="ODF900",
        )
    if manifest_schema:
        _validate_relaxng(
            trees,
            schema=Path(manifest_schema),
            member_names=("META-INF/manifest.xml",),
            report=report,
            rule_id="ODF901",
        )

    return report


def _audit_links(tree: etree._ElementTree, report: AuditReport) -> None:
    blocks = tree.xpath("//text:p | //text:h", namespaces=NS)
    for index, block in enumerate(blocks, start=1):
        text = _element_text(block)
        matches = list(URI_RE.finditer(text))
        if not matches:
            continue
        linked_texts = [_element_text(a) for a in block.xpath(".//text:a", namespaces=NS)]
        for match in matches:
            token, _suffix = split_trailing_punctuation(match.group(0))
            if not any(token in linked for linked in linked_texts):
                report.add(
                    "LNK001",
                    Severity.WARNING,
                    "Visible URL/email address is not represented by a hyperlink element.",
                    location=f"content.xml paragraph {index}",
                    details={"text": token},
                    fixable=True,
                )


def _audit_empty_spacers(
    tree: etree._ElementTree, package: OdtPackage, report: AuditReport
) -> None:
    catalog = StyleCatalog(package)
    empty = []
    for p in tree.xpath("//text:p", namespaces=NS):
        if not _is_empty_paragraph(p):
            continue
        if p.xpath(
            "ancestor::table:table-cell | ancestor::draw:text-box | ancestor::office:annotation",
            namespaces=NS,
        ):
            continue
        style_name = p.get(qn("text", "style-name"))
        empty.append((p, style_name, catalog.has_break_semantics(style_name)))
    if empty:
        report.add(
            "LAY001",
            Severity.INFO,
            (
                "Empty body paragraphs were found. If they are only visual "
                "spacers, prefer paragraph spacing instead."
            ),
            location="content.xml",
            details={
                "count": len(empty),
                "with_break_semantics": sum(item[2] for item in empty),
                "styles": sorted({item[1] or "(none)" for item in empty}),
            },
            fixable=True,
        )


def _audit_notes(tree: etree._ElementTree, report: AuditReport) -> None:
    notes = tree.xpath("//text:note", namespaces=NS)
    if notes:
        classes: dict[str, int] = {}
        for note in notes:
            cls = note.get(qn("text", "note-class")) or "unknown"
            classes[cls] = classes.get(cls, 0) + 1
        report.add(
            "SEM005",
            Severity.WARNING,
            (
                "Footnotes/endnotes are present; verify their reading order "
                "and PDF/UA export behaviour manually."
            ),
            location="content.xml",
            details={"count": len(notes), "classes": classes},
        )


def _audit_blinking(trees: dict[str, etree._ElementTree], report: AuditReport) -> None:
    found: list[str] = []
    for name in ("content.xml", "styles.xml"):
        found.extend(
            name for _ in trees[name].xpath("//*[@style:text-blinking='true']", namespaces=NS)
        )
    if found:
        report.add(
            "STYLE001",
            Severity.ERROR,
            "Blinking text styling is present.",
            location=", ".join(sorted(set(found))),
            fixable=False,
        )


def _audit_style_summary(package: OdtPackage, report: AuditReport) -> None:
    try:
        catalog = StyleCatalog(package)
        usage = catalog.paragraph_usage()
    except ValueError, KeyError:
        return
    report.metadata["paragraph_styles"] = [
        {
            "style": row.style_name,
            "count": row.count,
            "parent": row.parent,
            "spacing": row.spacing,
        }
        for row in usage
    ]
