# SPDX-License-Identifier: MPL-2.0
"""What a document family contributes: audit rules, operations, meaning-specific hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

lazy from odfa11y.outcomes import ReviewTopic

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from odfa11y.odf import Family, OdfDocument
    from odfa11y.report import Finding, Report

    from .operation import Operation


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """A judgement a person still has to make after the machine checks."""

    key: ReviewTopic
    text: str


class StyleUsage(TypedDict):
    """A style's usage count, parent and effective spacing in an adapter report."""

    style: str
    count: int
    parent: str | None
    spacing: dict[str, str]


@dataclass(frozen=True, slots=True)
class FamilyAdapter:
    """Everything the generic ODF core needs to know about one document family.

    The core understands OpenDocument structure; an adapter understands what a family's
    documents mean. ``family`` is None for the generic adapter that serves every kind
    without an implementation.
    """

    name: str
    family: Family | None
    audit: Callable[[OdfDocument, Report], None]
    default_language: Callable[[OdfDocument], str | None]
    set_default_language: Callable[[OdfDocument, str], bool]
    snapshot: Callable[[OdfDocument], tuple[str, ...]]
    preserved: Callable[[tuple[str, ...], tuple[str, ...], int], bool]
    config_tables: Mapping[str, Callable[[dict[str, object]], list[Operation]]]
    template: Callable[[Mapping[str, Sequence[Finding]]], list[str]]
    review_items: tuple[ReviewItem, ...]
    pdf_filter: str | None = None
    style_report: Callable[[OdfDocument], list[StyleUsage]] | None = None
    link_probe: Callable[[Path], Path] | None = None
    preflight: Callable[[OdfDocument, Sequence[Operation]], None] | None = None
    protect_edit: Callable[[OdfDocument, Operation], Callable[[], bool]] | None = None
