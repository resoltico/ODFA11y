# SPDX-License-Identifier: MPL-2.0
"""Frozen family capabilities and preservation contracts."""

from collections.abc import Callable
from dataclasses import dataclass

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.concepts.review import ReviewTopic
from odfa11y.decisions import DecisionKind
from odfa11y.odf import Family, OdfDocument
from odfa11y.odf.allowance import XmlChange
lazy from odfa11y.families.probes import CapabilityProbe
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class ReviewItem:
    key: ReviewTopic
    text: str


@dataclass(frozen=True, slots=True)
class PdfExport:
    filter: str


@dataclass(frozen=True, slots=True)
class Unsupported:
    reason: str


@dataclass(frozen=True, slots=True)
class LanguageTargets:
    read: Callable[[OdfDocument], str | None]
    write: Callable[[OdfDocument, str], XmlChange]


@dataclass(frozen=True, slots=True)
class FamilySpec:
    """The source semantics and explicit optional capabilities of one supported family."""

    family: Family
    audit: Callable[[OdfDocument, Report, DocumentMetadata], None]
    kinds: tuple[DecisionKind, ...]
    export: PdfExport | Unsupported
    language: LanguageTargets | None = None
    review_items: tuple[ReviewItem, ...] = ()
    probes: tuple[CapabilityProbe, ...] = ()
