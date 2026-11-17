# SPDX-License-Identifier: AGPL-3.0-only
"""Separate declared data/header relationships from unresolved visual table intent."""

from dataclasses import dataclass
from enum import StrEnum

lazy from lxml import etree

from odfa11y.concepts import declarations
from odfa11y.families.text.tables.grid import inspect_grid
from odfa11y.families.text.tables.headers import header_bands, relationships_cross_headers
from odfa11y.odf import names as xml_names
from odfa11y.odf import select_elements
lazy from odfa11y.families.text.tables.grid import Grid

DATA_TYPES = frozenset({"float", "percentage", "currency", "date", "time", "boolean"})


class TableKind(StrEnum):
    """Source-supported table intent; candidates are not asserted layout semantics."""

    DATA = "data"
    COMPLEX_DATA = "complex-data"
    LAYOUT_CANDIDATE = "layout-candidate"
    AMBIGUOUS = "ambiguous"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.DATA: "The table has explicit evidence of data-table intent.",
            self.COMPLEX_DATA: "The data table has relationships requiring explicit human review.",
            self.LAYOUT_CANDIDATE: (
                "The table may position content instead of expressing data relationships."
            ),
            self.AMBIGUOUS: "The table has insufficient evidence to infer data or layout intent.",
        }[self]


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
        cell.get(xml_names.OFFICE_VALUE_TYPE) in DATA_TYPES
        or xml_names.TABLE_FORMULA in cell.attrib
        for row in declarations(table, "rows")
        for cell in select_elements(row, "./table:table-cell")
    )
    if typed_data:
        return TableClassification(TableKind.DATA, grid, *headers)
    kind = TableKind.LAYOUT_CANDIDATE if min(grid.rows, grid.columns) <= 1 else TableKind.AMBIGUOUS
    return TableClassification(
        kind, grid, *headers, "Source declarations do not establish data-table intent."
    )
