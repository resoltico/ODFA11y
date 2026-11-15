# SPDX-License-Identifier: MPL-2.0
"""Run the read-only audit of an ODF document and collect its findings."""

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Annotated, Literal

from odfa11y.audit.metadata import audit_metadata
from odfa11y.audit.package import (
    audit_kind,
    audit_schema,
    audit_structure,
    audit_versions,
    storage_location,
)
from odfa11y.concepts.metadata import read_metadata
from odfa11y.contracts import Description
from odfa11y.errors import PackageError
from odfa11y.families import spec_for
from odfa11y.odf import OdfDocument, Part, Use, declared_version
from odfa11y.odf.export_context import native_export_limitations
from odfa11y.remediate.document_ops import document_question
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules

PARSED_PARTS = (Part.CONTENT, Part.STYLES, Part.META, Part.MANIFEST)
# Findings that end an audit early: what follows (and any plan made from it) would be guesswork.
BLOCKING_RULES = frozenset({
    rules.PKG000,
    rules.PKG005,
    rules.PKG006,
    rules.PKG007,
    rules.PKG009,
    rules.XML001,
    rules.ODF005,
    rules.ODF010,
})


@dataclass(frozen=True, slots=True)
class ExportContextMeasurements:
    """Measurements produced by export-context analysis; None denotes unmeasured data."""

    producer: Literal["export-context"] = field(default="export-context", init=False)
    limitations: Annotated[
        dict[str, int] | None,
        Description("Counts of declarations requiring native export refusal or review."),
    ] = None


def audit_odf(source: str | Path, *, schema: bool = False) -> Report:
    """Audit storage, document kind and semantics without modifying the source.

    Returns
    -------
    Report
        Package, kind and family findings, plus discovered metadata. With ``schema``, members
        are also validated against the bundled ODF schema for the declared version.

    """
    source = Path(source)
    report = Report(kind=ReportKind.ODF, subject=str(source), _sources=(source,))
    try:
        document = OdfDocument.open(source)
    except (PackageError, OSError) as exc:
        report.raise_(rules.PKG000, _describe(exc, source))
        return report

    return audit_document(document, subject=str(source), source=source, schema=schema)


def audit_document(
    document: OdfDocument, *, subject: str, source: Path | None = None, schema: bool = False
) -> Report:
    """Audit an existing document model, including an unpublished edited candidate."""
    report = Report(
        kind=ReportKind.ODF,
        subject=subject,
        _sources=(source,) if source else (),
    )
    protection = document.protection
    if protection.signatures:
        report.raise_(
            rules.PKG008,
            "Declared signatures are unverified: structure, references, cryptography and trust "
            "were not validated.",
            details={"members": list(protection.signatures)},
        )
    try:
        document.require(Use.AUDIT)
    except PackageError:
        if protection.malformed_manifest:
            report.raise_(rules.XML001, protection.malformed_manifest)
        elif protection.encrypted:
            report.raise_(rules.PKG009)
        else:
            audit_structure(document, report)
        return report
    if not audit_structure(document, report) or not audit_kind(document, report):
        return report
    if not _parseable(document, report):
        return report
    adapter = spec_for(document.kind)
    if adapter is None:
        report.raise_(
            rules.ODF009, "No supported source family; only package and structure checks ran."
        )
        if schema:
            audit_schema(document, report)
        return report

    analysis = read_metadata(document, adapter.language.read if adapter.language else None)
    report._question_for = partial(
        document_question, metadata=analysis.metadata, version=declared_version(document)
    )
    audit_versions(document, report)
    metadata = audit_metadata(analysis, report)
    adapter.audit(document, report, metadata)
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
            report.raise_(rules.XML001, str(exc), location=storage_location(document, part))
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
    report.measure(ExportContextMeasurements(limitations=limits))
    if limits["rendering_dependencies"]:
        report.raise_(rules.NATIVE001, details={"count": limits["rendering_dependencies"]})
    if limits["location_fields"]:
        report.raise_(rules.NATIVE002, details={"count": limits["location_fields"]})
