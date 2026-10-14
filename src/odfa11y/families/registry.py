# SPDX-License-Identifier: MPL-2.0
"""Which adapter serves which kind of document."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import UnsupportedKindError
from odfa11y.odf import Family, OdfDocument

from .chart import ADAPTER as CHART_ADAPTER
from .database import ADAPTER as DATABASE_ADAPTER
from .drawing import ADAPTER as DRAWING_ADAPTER
from .formula import ADAPTER as FORMULA_ADAPTER
from .generic import GENERIC
from .image import ADAPTER as IMAGE_ADAPTER
from .presentation import ADAPTER as PRESENTATION_ADAPTER
from .spreadsheet import ADAPTER as SPREADSHEET_ADAPTER
from .text import ADAPTER as TEXT_ADAPTER

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.adapter import FamilyAdapter, Operation, StyleUsage
    from odfa11y.odf import DocumentKind

REGISTRY: dict[Family, FamilyAdapter] = {
    Family.TEXT: TEXT_ADAPTER,
    Family.DATABASE: DATABASE_ADAPTER,
    Family.IMAGE: IMAGE_ADAPTER,
    Family.CHART: CHART_ADAPTER,
    Family.FORMULA: FORMULA_ADAPTER,
    Family.PRESENTATION: PRESENTATION_ADAPTER,
    Family.GRAPHICS: DRAWING_ADAPTER,
    Family.SPREADSHEET: SPREADSHEET_ADAPTER,
}


def adapter_for(kind: DocumentKind | None) -> FamilyAdapter:
    """Select the adapter for a document kind; kinds without one get the generic adapter.

    Returns
    -------
    FamilyAdapter
        The family's adapter, or the generic adapter.

    """
    return REGISTRY.get(kind.family, GENERIC) if kind is not None else GENERIC


def config_tables() -> dict[str, Callable[[dict[str, object]], list[Operation]]]:
    """Collect the plan tables every registered family reads.

    Returns
    -------
    dict[str, Callable[[dict[str, object]], list[Operation]]]
        Table name to the function turning that table into operations.

    """
    return {
        name: parse
        for adapter in REGISTRY.values()
        for name, parse in adapter.config_tables.items()
    }


def style_usage(source: str | Path) -> list[StyleUsage]:
    """Inspect paragraph styles through the source document family's supported hook.

    Returns
    -------
    list[StyleUsage]
        Style names, usage counts, parents and effective spacing.

    Raises
    ------
    UnsupportedKindError
        The family has no paragraph-style report.

    """
    document = OdfDocument.open(source)
    if document.protection.encrypted or document.protection.malformed_manifest:
        msg = "Protected or malformed package cannot establish style inspection."
        raise UnsupportedKindError(msg)
    style_report = adapter_for(document.kind).style_report
    if style_report is None:
        kind = document.kind.name if document.kind is not None else "unrecognised"
        msg = f"A style report is not defined for {kind} documents."
        raise UnsupportedKindError(msg)
    return style_report(document)
