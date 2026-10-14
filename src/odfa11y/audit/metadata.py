# SPDX-License-Identifier: MPL-2.0
"""Audit document title and language metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import normalize_language
from odfa11y.odf import NS, Part
from odfa11y.report import Location, rules

if TYPE_CHECKING:
    from odfa11y.adapter import FamilyAdapter
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_metadata(document: OdfDocument, adapter: FamilyAdapter, report: Report) -> None:
    """Report missing or empty title and language, with the family's default language."""
    meta = document.tree(Part.META) if document.has(Part.META) else None
    title = meta.findtext("office:meta/dc:title", namespaces=NS) if meta is not None else None
    if not title or not title.strip():
        report.add(
            rules.META001,
            "Document title metadata is missing.",
            location=Location("meta/title"),
        )
    else:
        report.metadata["title"] = title.strip()

    description = (
        meta.findtext("office:meta/dc:description", namespaces=NS) if meta is not None else None
    )
    if description and description.strip():
        report.metadata["description"] = description.strip()

    language = meta.findtext("office:meta/dc:language", namespaces=NS) if meta is not None else None
    _audit_language(document, adapter, report, language)


def _audit_language(
    document: OdfDocument, adapter: FamilyAdapter, report: Report, declared: str | None
) -> None:
    problems: dict[str, str] = {}
    language = _declared_language(declared, "metadata", problems)
    try:
        default_declared = adapter.default_language(document)
    except ValueError as exc:
        problems["default_style"] = str(exc)
        default_declared = None
    default_language = _declared_language(default_declared, "default_style", problems)
    if problems:
        report.add(rules.META004, location=Location("meta/language"), details=problems)
    if not language and not default_language:
        if not problems:
            report.add(
                rules.META002,
                "Document language is not declared in metadata or the default style.",
                location=Location("meta/language"),
            )
        return
    report.metadata["language"] = language or default_language
    if language and default_language and language.lower() != default_language.lower():
        report.add(
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
