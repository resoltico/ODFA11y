# SPDX-License-Identifier: MPL-2.0
"""Logical row/column declarations, repeats and spans in ODF tables."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from odfa11y.errors import RemediationError
from odfa11y.odf import NS, qn, select_elements

from .xml import attribute_bindings

if TYPE_CHECKING:
    from lxml import etree

AXES = {
    "rows": ("table-row", "table-header-rows", "number-rows-repeated"),
    "columns": ("table-column", "table-header-columns", "number-columns-repeated"),
}


def repeated(node: etree._Element, attribute: str) -> int:
    """Read a positive repeat/span count without expanding it.

    Returns
    -------
    int
        The declared positive count, defaulting to one.

    Raises
    ------
    RemediationError
        A declared count is malformed or non-positive.

    """
    value = node.get(qn("table", attribute), "1")
    if not value.isdecimal() or int(value) < 1:
        msg = f"Invalid table {attribute}: {value!r}"
        raise RemediationError(msg)
    return int(value)


def declarations(table: etree._Element, axis: str) -> list[etree._Element]:
    """Collect one table's declarations in order, excluding nested tables.

    Returns
    -------
    list[etree._Element]
        Physical declarations; each carries a logical repeat count.

    """
    tag = qn("table", AXES[axis][0])
    nodes = []
    for node in table.iter(tag):
        owner = next(node.iterancestors(qn("table", "table")), None)
        if owner is table:
            nodes.append(node)
    return nodes


def axis_count(table: etree._Element, axis: str) -> int:
    """Count logical rows or columns.

    Returns
    -------
    int
        Total repetitions across the table's declarations.

    """
    return sum(repeated(node, AXES[axis][2]) for node in declarations(table, axis))


def header_count(table: etree._Element, axis: str) -> int:
    """Count leading logical headers, rejecting non-leading header bands.

    Returns
    -------
    int
        The existing leading header count.

    Raises
    ------
    RemediationError
        A grouped/non-leading header band cannot be represented by one leading count.

    """
    header = qn("table", AXES[axis][1])
    total = 0
    data_seen = False
    for node in declarations(table, axis):
        marked = any(
            parent.tag == header and next(parent.iterancestors(qn("table", "table")), None) is table
            for parent in node.iterancestors()
        )
        if marked and data_seen:
            msg = "Non-leading table header bands require an explicit group-level decision."
            raise RemediationError(msg)
        if marked:
            total += repeated(node, AXES[axis][2])
        else:
            data_seen = True
    return total


def require_safe_boundary(table: etree._Element, rows: int | None, columns: int | None) -> None:
    """Refuse crossing spans or a repeat split that duplicates structural identities.

    Raises
    ------
    RemediationError
        A merged cell crosses the boundary or a repeat/span is malformed.

    """
    row_position = 0
    _require_splittable_columns(table, columns)
    for row in declarations(table, "rows"):
        row_repeat = repeated(row, "number-rows-repeated")
        if rows is not None and row_position < rows < row_position + row_repeat:
            _require_splittable(row)
        column_position = 0
        for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell"):
            span_rows = repeated(cell, "number-rows-spanned")
            span_columns = repeated(cell, "number-columns-spanned")
            row_crosses = _crosses(row_position, row_repeat, span_rows, rows)
            column_crosses = _crosses(
                column_position, repeated(cell, "number-columns-repeated"), span_columns, columns
            )
            if row_crosses or column_crosses:
                msg = "A merged cell crosses the requested header boundary."
                raise RemediationError(msg)
            column_position += repeated(cell, "number-columns-repeated")
        row_position += row_repeat


def table_fingerprint(table: etree._Element) -> str:
    """Fingerprint full table data without header-wrapper or description metadata.

    Returns
    -------
    str
        The reviewed table identity and all protected rows/cell attributes and words.

    """
    return _fingerprint(table, include_styles=True)


def table_content_fingerprint(table: etree._Element) -> str:
    """Fingerprint logical data independently of generated style names.

    Returns
    -------
    str
        Protected words, values, formulas and grid structure.

    """
    return _fingerprint(table, include_styles=False)


def _attributes(node: etree._Element, repeat: str, *, include_styles: bool) -> dict[str, str]:
    excluded = {qn("table", repeat)}
    if not include_styles:
        excluded.add(qn("table", "style-name"))
    return {k: v for k, v in node.attrib.items() if k not in excluded}


def _fingerprint(table: etree._Element, *, include_styles: bool) -> str:
    columns = []
    for column in declarations(table, "columns"):
        count = repeated(column, "number-columns-repeated")
        attributes = _attributes(column, "number-columns-repeated", include_styles=include_styles)
        if columns and columns[-1][0] == attributes:
            columns[-1] = (attributes, columns[-1][1] + count)
        else:
            columns.append((attributes, count))
    facts = [table.get(qn("table", "name")), columns]
    runs: list[tuple[object, int]] = []
    for row in declarations(table, "rows"):
        cells = []
        for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell"):
            words = cell.xpath(
                "descendant::text()[not(ancestor::svg:title or ancestor::svg:desc "
                "or ancestor::office:binary-data)]",
                namespaces=NS,
            )
            cells.append([
                cell.tag,
                attribute_bindings(
                    cell,
                    omitted_attributes=() if include_styles else (qn("table", "style-name"),),
                ),
                _attributes(cell, "unused", include_styles=include_styles),
                " ".join("".join(str(word) for word in words).split()),
            ])
        attributes = _attributes(row, "number-rows-repeated", include_styles=include_styles)
        value = [
            attributes,
            attribute_bindings(row, omitted_attributes=(qn("table", "number-rows-repeated"),)),
            cells,
        ]
        count = repeated(row, "number-rows-repeated")
        if runs and runs[-1][0] == value:
            runs[-1] = (value, runs[-1][1] + count)
        else:
            runs.append((value, count))
    facts.extend(runs)
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]


def _crosses(position: int, count: int, span: int, boundary: int | None) -> bool:
    return boundary is not None and span > 1 and position < boundary < position + count - 1 + span


def _require_splittable_columns(table: etree._Element, boundary: int | None) -> None:
    position = 0
    for column in declarations(table, "columns"):
        count = repeated(column, "number-columns-repeated")
        if boundary is not None and position < boundary < position + count:
            _require_splittable(column)
        position += count


def _require_splittable(declaration: etree._Element) -> None:
    identities = {"{http://www.w3.org/XML/1998/namespace}id", qn("draw", "id")}
    structures = {qn("text", "h"), qn("draw", "frame"), qn("table", "table")}
    if any(
        node.tag in structures or identities.intersection(node.attrib)
        for node in declaration.iter()
    ):
        msg = "Splitting this repeat would duplicate structural objects or identities."
        raise RemediationError(msg)
