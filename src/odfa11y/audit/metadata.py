# SPDX-License-Identifier: MPL-2.0
"""Audit document title and language metadata."""

from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, Part
from odfa11y.report import FactKeys, Location
from odfa11y.rules import registry as rules
lazy from odfa11y.families.spec import FamilySpec
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


def audit_metadata(document: OdfDocument, adapter: FamilySpec, report: Report) -> None:
    """Report missing or empty title and language, with the family's default language."""
    meta = document.tree(Part.META) if document.has(Part.META) else None
    title = meta.findtext("office:meta/dc:title", namespaces=NS) if meta is not None else None
    if title and title.strip():
        report.facts[FactKeys.DOCUMENT_TITLE] = title.strip()

    description = (
        meta.findtext("office:meta/dc:description", namespaces=NS) if meta is not None else None
    )
    if description and description.strip():
        report.facts[FactKeys.DOCUMENT_DESCRIPTION] = description.strip()

    language = meta.findtext("office:meta/dc:language", namespaces=NS) if meta is not None else None
    _audit_language(document, adapter, report, language)
    if not title or not title.strip():
        report.raise_(
            rules.META001, "Document title metadata is missing.", location=Location("meta/title")
        )


def _audit_language(
    document: OdfDocument, adapter: FamilySpec, report: Report, declared: str | None
) -> None:
    problems: dict[str, str] = {}
    language = _declared_language(declared, "metadata", problems)
    try:
        default_declared = adapter.language.read(document) if adapter.language is not None else None
    except ValueError as exc:
        problems["default_style"] = str(exc)
        default_declared = None
    default_language = _declared_language(default_declared, "default_style", problems)
    if problems:
        report.raise_(rules.META004, location=Location("meta/language"), details=problems)
    if not language and not default_language:
        if not problems:
            report.raise_(
                rules.META002,
                "Document language is not declared in metadata or the default style.",
                location=Location("meta/language"),
            )
        return
    report.facts[FactKeys.DOCUMENT_LANGUAGE] = language or default_language
    if language and default_language and language.lower() != default_language.lower():
        report.raise_(
            rules.META003,
            location=Location("meta/language"),
            details={"metadata": declared, "default_style": default_declared},
        )


def _declared_language(value: str | None, source: str, problems: dict[str, str]) -> str | None:
    if not value or not value.strip():
        return None
    try:
        return normalize_language(value)
    except ValueError as exc:
        problems[source] = str(exc)
        return None
