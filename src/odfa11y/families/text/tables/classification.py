# SPDX-License-Identifier: MPL-2.0
"""Separate declared data/header relationships from unresolved visual table intent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from odfa11y.content import declarations
from odfa11y.odf import qn, select_elements

from .grid import inspect_grid
from .headers import header_bands, relationships_cross_headers

if TYPE_CHECKING:
    from lxml import etree

    from .grid import Grid

DATA_TYPES = frozenset({"float", "percentage", "currency", "date", "time", "boolean"})


class TableKind(StrEnum):
    """Source-supported table intent; candidates are not asserted layout semantics."""

    DATA = "data"
    COMPLEX_DATA = "complex-data"
    LAYOUT_CANDIDATE = "layout-candidate"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class TableClassification:
    """Grid evidence, header bands and the remaining intent/relationship uncertainty."""

    kind: TableKind
    grid: Grid
    header_rows: int
    header_columns: int
    reason: str | None = None


def classify(table: etree._Element) -> TableClassification:
    """Use declared values and semantic bands, without label-length or merge heuristics.

    Returns
    -------
    TableClassification
        Proven data relationships or an explicit intent-review classification.

    """
    grid = inspect_grid(table)
    row_bands, column_bands = header_bands(table, "rows"), header_bands(table, "columns")
    headers = row_bands.count, column_bands.count
    if any(headers):
        if grid.complex and relationships_cross_headers(table, row_bands, column_bands):
            return TableClassification(
                TableKind.AMBIGUOUS,
                grid,
                *headers,
                "Merged origin crosses an actual semantic header/data boundary.",
            )
        complex_relationships = grid.complex or not (row_bands.leading and column_bands.leading)
        kind = TableKind.COMPLEX_DATA if complex_relationships else TableKind.DATA
        return TableClassification(kind, grid, *headers)
    typed_data = any(
        cell.get(qn("office", "value-type")) in DATA_TYPES or qn("table", "formula") in cell.attrib
        for row in declarations(table, "rows")
        for cell in select_elements(row, "./table:table-cell")
    )
    if typed_data:
        return TableClassification(TableKind.DATA, grid, *headers)
    kind = TableKind.LAYOUT_CANDIDATE if min(grid.rows, grid.columns) <= 1 else TableKind.AMBIGUOUS
    return TableClassification(
        kind, grid, *headers, "Source declarations do not establish data-table intent."
    )
