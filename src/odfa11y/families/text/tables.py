# SPDX-License-Identifier: MPL-2.0
"""Set reviewed leading row and column header boundaries in text tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import axis_count, header_count, require_safe_boundary, table_fingerprint
from odfa11y.errors import RemediationError
from odfa11y.odf import Family, Part, qn, select_elements

from .table_edit import mark_axis

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lxml import etree

    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class TableHeaders:
    """Explicit leading counts; absent axes keep their existing semantics."""

    rows: int | None = None
    columns: int | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class MarkTableHeaders(Operation):
    """Preflight all tables and mark the explicitly selected header axes."""

    entries: Mapping[str, TableHeaders]
    name: ClassVar[str] = "mark_table_headers"
    family: ClassVar[Family | None] = Family.TEXT

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        tables = select_elements(document.tree(Part.CONTENT), "//office:body//table:table")
        plans = []
        failures = []
        for name, entry in self.entries.items():
            matches = [table for table in tables if table.get(qn("table", "name")) == name]
            try:
                changes = _preflight(matches, entry)
                plans.append((name, matches[0], changes))
            except RemediationError as exc:
                failures.append(Outcome(self.name, Status.FAILED, str(exc), key=name))
        if failures:
            return tuple(failures)
        outcomes = []
        for name, table, changes in plans:
            for axis, count in changes.items():
                mark_axis(table, axis, count)
            if changes:
                document.edit(Part.CONTENT)
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if changes else Status.UNCHANGED,
                    "Applied reviewed table headers."
                    if changes
                    else "Table headers already match.",
                    key=name,
                    count=len(changes),
                )
            )
        return tuple(outcomes)


def _preflight(matches: list[etree._Element], entry: TableHeaders) -> dict[str, int]:
    """Resolve a unique target and prove both requested boundaries are safe.

    Returns
    -------
    dict[str, int]
        Only the axes that need a change.

    Raises
    ------
    RemediationError
        A target/count/boundary is ambiguous, stale, invalid or unavailable.

    """
    if len(matches) != 1:
        msg = "The table name must resolve to exactly one table."
        raise RemediationError(msg)
    table = matches[0]
    if entry.fingerprint is not None and entry.fingerprint != table_fingerprint(table):
        msg = "The table is no longer the object this plan was reviewed against."
        raise RemediationError(msg)
    if entry.rows is None and entry.columns is None:
        msg = "A table-header decision needs rows or columns."
        raise RemediationError(msg)
    changes = {}
    for axis, count in [("rows", entry.rows), ("columns", entry.columns)]:
        if count is None:
            continue
        if type(count) is not int or count < 1 or count > axis_count(table, axis):
            msg = f"Header {axis} must be a positive count within the table."
            raise RemediationError(msg)
        if header_count(table, axis) != count:
            changes[axis] = count
    require_safe_boundary(table, entry.rows, entry.columns)
    return changes
