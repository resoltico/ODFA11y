# SPDX-License-Identifier: MPL-2.0
"""Audit document title and language metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, Part
from odfa11y.report import rules

if TYPE_CHECKING:
    from odfa11y.adapter import FamilyAdapter
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_metadata(document: OdfDocument, adapter: FamilyAdapter, report: Report) -> None:
    """Report missing or empty title and language, with the family's default language."""
    meta = document.tree(Part.META) if document.has(Part.META) else None
    meta_name = document.member_name(Part.META) or Part.META.value
    title = meta.findtext(".//dc:title", namespaces=NS) if meta is not None else None
    if not title or not title.strip():
        report.add(rules.META001, "Document title metadata is missing.", location=meta_name)
    else:
        report.metadata["title"] = title.strip()

    language = meta.findtext(".//dc:language", namespaces=NS) if meta is not None else None
    default_language = adapter.default_language(document)
    if not (language and language.strip()) and not default_language:
        report.add(
            rules.META002,
            "Document language is not declared in metadata or the default style.",
            location=meta_name,
        )
        return
    report.metadata["language"] = (language or default_language or "").strip()
    if (
        language
        and default_language
        and _normalize_lang(language) != _normalize_lang(default_language)
    ):
        report.add(
            rules.META003,
            location=meta_name,
            details={"metadata": language, "default_style": default_language},
        )


def _normalize_lang(value: str) -> str:
    return value.replace("_", "-").lower()
