# SPDX-License-Identifier: MPL-2.0
"""What a document family contributes: audit rules, operations, meaning-specific hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from odfa11y.odf import Family, OdfDocument
    from odfa11y.report import Finding, Report

    from .operation import Operation


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """A judgement a person still has to make after the machine checks."""

    key: str
    text: str


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
    set_default_language: Callable[[OdfDocument, str, str | None], bool]
    snapshot: Callable[[OdfDocument], tuple[str, ...]]
    preserved: Callable[[tuple[str, ...], tuple[str, ...], int], bool]
    config_tables: Mapping[str, Callable[[dict[str, object]], list[Operation]]]
    template: Callable[[Mapping[str, Sequence[Finding]]], list[str]]
    review_items: tuple[ReviewItem, ...]
    pdf_filter: str | None = None
    style_report: Callable[[OdfDocument], list[dict[str, object]]] | None = None
