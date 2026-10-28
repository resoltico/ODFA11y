# SPDX-License-Identifier: MPL-2.0
"""Report table intent and header relationships from source declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import table_fingerprint
from odfa11y.decisions import OpenDecision
from odfa11y.errors import RemediationError
from odfa11y.families.text.contexts import context_location, text_nodes
from odfa11y.families.text.decisions import TABLE_HEADERS
from odfa11y.odf import Part, qn
from odfa11y.report import FactKeys, rules

from .classification import TableKind, classify

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

NATIVE_GUIDANCE = (
    "Review table intent and header relationships in Writer; no layout/data conversion is inferred."
)


def audit_tables(document: OdfDocument, report: Report) -> None:
    """Audit actual grid and band relationships, preserving ambiguous table intent."""
    tables = text_nodes(document.tree(Part.CONTENT), qn("table", "table"))
    report.facts[FactKeys.TEXT_TABLE_COUNT] = len(tables)
    rows: list[dict[str, object]] = []
    for index, table in enumerate(tables, 1):
        name = table.get(qn("table", "name"))
        location = context_location(table, "table", index, name)
        try:
            classification = classify(table)
        except RemediationError as error:
            report.add(
                rules.TABLE002,
                str(error),
                location=location,
                details={"native_editing": NATIVE_GUIDANCE},
            )
            rows.append({
                "target": location.path,
                "classification": "unresolved",
                "reason": str(error),
            })
            continue
        rows.append({
            "target": location.path,
            "classification": classification.kind.value,
            "rows": classification.grid.rows,
            "columns": classification.grid.columns,
            "header_rows": classification.header_rows,
            "header_columns": classification.header_columns,
        })
        if classification.kind in {TableKind.LAYOUT_CANDIDATE, TableKind.AMBIGUOUS}:
            report.add(
                rules.TABLE001,
                classification.reason,
                location=location,
                details={
                    "classification": classification.kind.value,
                    "native_editing": NATIVE_GUIDANCE,
                },
            )
        elif not (classification.header_rows or classification.header_columns):
            report.add(
                rules.TABLE003,
                location=location,
                details={"table": name, "rows": classification.grid.rows},
            )
            report.add_decision(
                OpenDecision(
                    TABLE_HEADERS,
                    location,
                    table_fingerprint(table, document),
                    {"rows": 0, "columns": 0},
                    (rules.TABLE003.id,),
                )
            )
    report.facts[FactKeys.TEXT_TABLE_CLASSIFICATIONS] = rows
