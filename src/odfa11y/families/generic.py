# SPDX-License-Identifier: MPL-2.0
"""The adapter for document kinds without a family implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import body_text_snapshot
from odfa11y.report import rules

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Finding, Report

REVIEW_ITEMS = (
    ReviewItem("alt text", "Whether every graphic's description is meaningful in its context."),
    ReviewItem("reading order", "Whether the reading order of the content is logical."),
    ReviewItem("colour", "Whether colour conveys information that is not available any other way."),
    ReviewItem("layout", "Whether the pages look right: typography and visual appearance."),
)


def _audit(document: OdfDocument, report: Report) -> None:
    kind = document.kind
    label = kind.name if kind is not None else "unrecognised"
    report.add(
        rules.ODF009,
        f"No semantic audit exists for {label} documents; only package, version, metadata and "
        "schema checks ran.",
    )


def _no_default_language(document: OdfDocument) -> str | None:
    del document
    return None


def _no_language_target(document: OdfDocument, tag: str) -> bool:
    del document, tag
    return False


def _no_template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    del by_remedy
    return []


def _unchanged(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    return removed_blocks == 0 and before == after


GENERIC = FamilyAdapter(
    name="generic",
    family=None,
    audit=_audit,
    default_language=_no_default_language,
    set_default_language=_no_language_target,
    snapshot=body_text_snapshot,
    preserved=_unchanged,
    config_tables={},
    template=_no_template,
    review_items=REVIEW_ITEMS,
)
