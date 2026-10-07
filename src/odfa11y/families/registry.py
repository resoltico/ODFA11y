# SPDX-License-Identifier: MPL-2.0
"""Which adapter serves which kind of document."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import Family

from .drawing import ADAPTER as DRAWING_ADAPTER
from .generic import GENERIC
from .presentation import ADAPTER as PRESENTATION_ADAPTER
from .spreadsheet import ADAPTER as SPREADSHEET_ADAPTER
from .text import ADAPTER as TEXT_ADAPTER

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.adapter import FamilyAdapter, Operation
    from odfa11y.odf import DocumentKind

REGISTRY: dict[Family, FamilyAdapter] = {
    Family.TEXT: TEXT_ADAPTER,
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
