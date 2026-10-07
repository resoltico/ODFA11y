# SPDX-License-Identifier: MPL-2.0
"""Mark leading table rows as semantic header rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.odf import qn, select_elements

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdtDocument


@dataclass(frozen=True, slots=True)
class MarkHeaderRows(Operation):
    """Wrap the first N direct rows of each named table in ``table:table-header-rows``."""

    rows: Mapping[str, int]
    name: ClassVar[str] = "mark_header_rows"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        tables = select_elements(document.tree("content.xml"), "//table:table")
        by_name = {table.get(qn("table", "name")): table for table in tables}
        return tuple(
            self._mark(document, name, by_name.get(name), count)
            for name, count in self.rows.items()
        )

    @override
    def as_dict(self) -> dict[str, object]:
        return {"operation": self.name, "rows": dict(self.rows)}

    def _mark(
        self, document: OdtDocument, name: str, table: etree._Element | None, count: int
    ) -> Outcome:
        if table is None:
            return Outcome(self.name, Status.FAILED, f"No table is named {name!r}.", key=name)
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
        document.edit("content.xml")
        wrapper = etree.Element(qn("table", "table-header-rows"))
        table.insert(table.index(rows[0]), wrapper)
        for row in rows[:count]:
            wrapper.append(row)
        return Outcome(
            self.name, Status.APPLIED, f"Marked {count} header row(s).", key=name, count=count
        )
