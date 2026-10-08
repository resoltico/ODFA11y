# SPDX-License-Identifier: MPL-2.0
"""Run the read-only audit of an ODF document and collect its findings."""

from __future__ import annotations

from pathlib import Path

from odfa11y.content import native_export_limitations
from odfa11y.errors import PackageError
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument, Part
from odfa11y.report import Report, rules

from .metadata import audit_metadata
from .package import (
    audit_kind,
    audit_schema,
    audit_structure,
    audit_versions,
    storage_location,
)

PARSED_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.MANIFEST)
# Findings that end an audit early: what follows (and any plan made from it) would be guesswork.
BLOCKING_RULE_IDS = frozenset({
    rules.PKG000.id,
    rules.PKG005.id,
    rules.XML001.id,
    rules.ODF005.id,
    rules.ODF010.id,
})


def audit_odf(source: str | Path, *, schema: bool = False) -> Report:
    """Audit storage, document kind and semantics without modifying the source.

    Returns
    -------
    Report
        Package, kind and family findings, plus discovered metadata. With ``schema``, members
        are also validated against the bundled ODF schema for the declared version.

    """
    source = Path(source)
    report = Report(kind="odf", subject=str(source), sources=(source,))
    try:
        document = OdfDocument.open(source)
    except (PackageError, OSError) as exc:
        report.add(rules.PKG000, _describe(exc, source))
        return report

    if not audit_structure(document, report) or not audit_kind(document, report):
        return report
    if not _parseable(document, report):
        return report
    adapter = adapter_for(document.kind)
    report.metadata["adapter"] = adapter.name
    audit_versions(document, report)
    audit_metadata(document, adapter, report)
    adapter.audit(document, report)
    _audit_export_context(document, report)
    if schema:
        audit_schema(document, report)
    return report


def _parseable(document: OdfDocument, report: Report) -> bool:
    ok = True
    seen: set[str] = set()
    for part in (*PARSED_PARTS, Part.SETTINGS):
        name = document.member_name(part)
        if name is None or name in seen:
            continue
        seen.add(name)
        try:
            document.tree(part)
        except PackageError as exc:
            report.add(rules.XML001, str(exc), location=storage_location(document, part))
            ok = ok and part is Part.SETTINGS
    return ok


def _describe(exc: PackageError | OSError, source: Path) -> str:
    """Describe an open failure without the file's directory.

    Returns
    -------
    str
        The failure with only the file name, so reports never carry local paths.

    """
    if isinstance(exc, OSError) and not isinstance(exc, PackageError):
        return f"Cannot read {source.name}: {exc.strerror or type(exc).__name__}"
    return str(exc)


def _audit_export_context(document: OdfDocument, report: Report) -> None:
    limits = native_export_limitations(document)
    report.metadata["native_export_limitations"] = limits
    if limits["rendering_dependencies"]:
        report.add(rules.ODF012, details={"count": limits["rendering_dependencies"]})
    if limits["location_fields"]:
        report.add(rules.ODF013, details={"count": limits["location_fields"]})
