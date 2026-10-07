# SPDX-License-Identifier: MPL-2.0
"""Mark leading table rows as semantic header rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import Family, Part, qn, select_elements

from .fingerprint import table_fingerprint

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class HeaderRows:
    """How many leading rows are headers; ``fingerprint`` guards against document drift."""

    count: int
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class MarkHeaderRows(Operation):
    """Wrap the first N direct rows of each named table in ``table:table-header-rows``."""

    entries: Mapping[str, HeaderRows]
    name: ClassVar[str] = "mark_header_rows"
    family: ClassVar[Family | None] = Family.TEXT

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        tables = select_elements(document.tree(Part.CONTENT), "//table:table")
        return tuple(
            self._mark(
                document,
                name,
                [table for table in tables if table.get(qn("table", "name")) == name],
                entry,
            )
            for name, entry in self.entries.items()
        )

    @override
    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.name,
            "entries": {
                name: {"rows": entry.count, "fingerprint": entry.fingerprint}
                for name, entry in self.entries.items()
            },
        }

    def _mark(
        self, document: OdfDocument, name: str, matches: list[etree._Element], entry: HeaderRows
    ) -> Outcome:
        count = entry.count
        if not matches:
            return Outcome(self.name, Status.FAILED, f"No table is named {name!r}.", key=name)
        if len(matches) > 1:
            message = f"{len(matches)} tables are named {name!r}; the name must be unique."
            return Outcome(self.name, Status.FAILED, message, key=name)
        table = matches[0]
        if entry.fingerprint is not None and entry.fingerprint != table_fingerprint(table):
            message = "The table is no longer the object this plan was reviewed against."
            return Outcome(self.name, Status.FAILED, message, key=name)
        return self._wrap(document, name, table, count)

    def _wrap(self, document: OdfDocument, name: str, table: etree._Element, count: int) -> Outcome:
        existing = select_elements(table, "./table:table-header-rows/table:table-row")
        if existing:
            if len(existing) == count:
                return Outcome(
                    self.name, Status.UNCHANGED, f"Already has {count} header row(s).", key=name
                )
            message = f"Already has {len(existing)} header row(s), not {count}."
            return Outcome(self.name, Status.FAILED, message, key=name)
        rows = select_elements(table, "./table:table-row")
        if len(rows) < count:
            message = f"Has only {len(rows)} direct row(s), not {count}."
            return Outcome(self.name, Status.FAILED, message, key=name)
        document.edit(Part.CONTENT)
        wrapper = etree.Element(qn("table", "table-header-rows"))
        table.insert(table.index(rows[0]), wrapper)
        for row in rows[:count]:
            wrapper.append(row)
        return Outcome(
            self.name, Status.APPLIED, f"Marked {count} header row(s).", key=name, count=count
        )
