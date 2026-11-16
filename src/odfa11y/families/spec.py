# SPDX-License-Identifier: MPL-2.0
"""Frozen family capabilities and preservation contracts."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.concepts.preservation import PreservationSnapshot
from odfa11y.concepts.review import ReviewTopic
from odfa11y.decisions import Decision, DecisionKind
from odfa11y.decisions.edit import Outcome
from odfa11y.odf import Family, OdfDocument
from odfa11y.odf.allowance import XmlChange
lazy from odfa11y.native.probes import CapabilityProbe
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


def _preserved(
    before: PreservationSnapshot, after: PreservationSnapshot, outcomes: Sequence[Outcome]
) -> bool:
    return before == after


def _preflight(document: OdfDocument, decisions: Sequence[Decision]) -> None:
    pass


def _protect_edit(document: OdfDocument, decision: Decision) -> Callable[[], bool] | None:
    return None


@dataclass(frozen=True, slots=True)
class FamilySpec:
    """The source semantics and explicit optional capabilities of one supported family."""

    family: Family
    audit: Callable[[OdfDocument, Report, DocumentMetadata], None]
    kinds: tuple[DecisionKind, ...]
    export: PdfExport | Unsupported
    snapshot: Callable[[OdfDocument], PreservationSnapshot]
    language: LanguageTargets | None = None
    review_items: tuple[ReviewItem, ...] = ()
    probes: tuple[CapabilityProbe, ...] = ()
    preserved: Callable[[PreservationSnapshot, PreservationSnapshot, Sequence[Outcome]], bool] = (
        _preserved
    )
    preflight: Callable[[OdfDocument, Sequence[Decision]], None] = _preflight
    protect_edit: Callable[[OdfDocument, Decision], Callable[[], bool] | None] = _protect_edit
