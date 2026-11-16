# SPDX-License-Identifier: AGPL-3.0-only
"""Typed document metadata and language analysis shared by source audits."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Literal

from odfa11y.contracts import Description
from odfa11y.errors import DocumentRefusal
from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, OdfDocument, Part


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    producer: Literal["odf-metadata"] = field(default="odf-metadata", init=False)
    title: Annotated[str | None, Description("Document title.")] = None
    description: Annotated[str | None, Description("Authored document description.")] = None
    language: Annotated[str | None, Description("Effective document language.")] = None


@dataclass(frozen=True, slots=True)
class MetadataAnalysis:
    metadata: DocumentMetadata
    declared: str | None
    default: str | None
    metadata_problem: str | None = None
    default_problem: str | None = None
    declared_language: str | None = None
    default_language: str | None = None


def read_metadata(
    document: OdfDocument, default_reader: Callable[[OdfDocument], str | None] | None
) -> MetadataAnalysis:
    meta = document.tree(Part.META) if document.has(Part.META) else None
    title = meta.findtext("office:meta/dc:title", namespaces=NS) if meta is not None else None
    description = (
        meta.findtext("office:meta/dc:description", namespaces=NS) if meta is not None else None
    )
    declared = meta.findtext("office:meta/dc:language", namespaces=NS) if meta is not None else None
    language, metadata_problem = _language(declared)
    default = None
    default_problem = None
    try:
        default = default_reader(document) if default_reader is not None else None
    except (ValueError, DocumentRefusal) as error:
        default_problem = str(error)
    default_language, tag_problem = _language(default)
    return MetadataAnalysis(
        DocumentMetadata(
            title.strip() if title and title.strip() else None,
            description.strip() if description and description.strip() else None,
            language or default_language,
        ),
        declared,
        default,
        metadata_problem,
        default_problem or tag_problem,
        language,
        default_language,
    )


def _language(value: str | None) -> tuple[str | None, str | None]:
    if not value or not value.strip():
        return None, None
    try:
        return normalize_language(value), None
    except ValueError as error:
        return None, str(error)
