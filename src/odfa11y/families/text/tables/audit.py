# SPDX-License-Identifier: AGPL-3.0-only
"""Report table intent and header relationships from source declarations."""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.domains import TABLES
from odfa11y.families.text.kinds import TABLE_HEADERS
from odfa11y.families.text.tables.classification import TableKind, classify
from odfa11y.odf import names as xml_names
from odfa11y.rules import registry as rules
from odfa11y.targets import Location, TargetPath
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

NATIVE_GUIDANCE = (
    "Review table intent and header relationships in Writer; no layout/data conversion is inferred."
)


@dataclass(frozen=True, slots=True)
class MeasuredTable:
    target: TargetPath
    classification: TableKind
    rows: int
    columns: int
    header_rows: int
    header_columns: int
    state: Literal["measured"] = field(default="measured", init=False)


@dataclass(frozen=True, slots=True)
class UnresolvedTable:
    target: TargetPath
    reason: str
    state: Literal["unresolved"] = field(default="unresolved", init=False)


@dataclass(frozen=True, slots=True)
class TableMeasurements:
    """Measurements produced by text-tables analysis; None denotes unmeasured data."""

    producer: Literal["text-tables"] = field(default="text-tables", init=False)
    table_count: Annotated[int | None, Description("Tables in current reading contexts.")] = None
    table_classifications: Annotated[
        list[MeasuredTable | UnresolvedTable] | None,
        Description("Per-table source-supported intent, grid and semantic header bands."),
    ] = None


def audit_tables(document: OdfDocument, report: Report) -> None:
    """Audit actual grid and band relationships, preserving ambiguous table intent."""
    entries = tuple(TABLES.enumerate(document))
    tables = [node for _, node in entries]
    if tables:
        report.observe_review(Topic.TABLE_HEADERS)
    report.measure(TableMeasurements(table_count=len(tables)))
    rows: list[MeasuredTable | UnresolvedTable] = []
    for path, table in entries:
        name = table.get(xml_names.TABLE_NAME)
        location = Location(path)
        try:
            classification = classify(table)
        except DocumentRefusal as error:
            report.raise_(
                rules.TABLE002,
                str(error),
                location=location,
                details={"native_editing": NATIVE_GUIDANCE},
            )
            rows.append(UnresolvedTable(location.path, str(error)))
            continue
        rows.append(
            MeasuredTable(
                location.path,
                classification.kind,
                classification.grid.rows,
                classification.grid.columns,
                classification.header_rows,
                classification.header_columns,
            )
        )
        if classification.kind in {TableKind.LAYOUT_CANDIDATE, TableKind.AMBIGUOUS}:
            report.raise_(
                rules.TABLE001,
                classification.reason,
                location=location,
                details={
                    "classification": classification.kind.value,
                    "native_editing": NATIVE_GUIDANCE,
                },
            )
        elif not (classification.header_rows or classification.header_columns):
            report.raise_(
                rules.TABLE003,
                location=location,
                details={"table": name, "rows": classification.grid.rows},
                decision=OpenDecision(
                    TABLE_HEADERS,
                    TABLES.binding(document, path),
                    {"rows": 0, "columns": 0},
                ),
            )
    report.measure(TableMeasurements(table_classifications=rows))
