# SPDX-License-Identifier: MPL-2.0
"""Audit standalone chart identity, descriptions, cached ranges and labels."""

from typing import Annotated, Literal
lazy from dataclasses import dataclass, field

from lxml import etree

from odfa11y.concepts import visible_words
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.contracts import Description
from odfa11y.errors import DocumentRefusal
from odfa11y.families.chart.ranges import range_shape, resolve_range
from odfa11y.odf import Part, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.families.chart.ranges import LocalRange
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class ChartMeasurements:
    """Measurements produced by chart analysis; None denotes unmeasured data."""

    producer: Literal["chart"] = field(default="chart", init=False)
    count: Annotated[int | None, Description("Native charts in a Chart document.")] = None
    series_count: Annotated[int | None, Description("Declared chart series.")] = None


def audit_chart(document: OdfDocument, report: Report, metadata: DocumentMetadata) -> None:
    """Inspect source semantics without loading external data or inventing an export filter."""
    charts = select_elements(document.tree(Part.CONTENT), "//office:body/office:chart/chart:chart")
    report.measure(ChartMeasurements(count=len(charts)))
    location = Location(f"{Part.CONTENT}/chart")
    if len(charts) != 1:
        report.raise_(rules.CHART001, location=location)
        return
    chart = charts[0]
    if not metadata.title and not any(
        visible_words(node) for node in select_elements(chart, "./chart:title")
    ):
        report.raise_(rules.CHART002, location=location)
    if not metadata.description:
        report.raise_(rules.CHART003, location=Location("meta/description"))
    series = select_elements(chart, "./chart:plot-area/chart:series")
    report.measure(ChartMeasurements(series_count=len(series)))
    if not series:
        report.raise_(rules.CHART001, "The chart declares no data series.", location=location)
    _ranges(chart, report)
    _series_consistency(chart, report)
    labels = select_elements(
        chart,
        "./table:table//table:table-cell[@office:value-type='string']/text:p "
        "| .//chart:title/text:p",
    )
    if not any(visible_words(label) for label in labels):
        report.raise_(
            rules.CHART006,
            "Chart has no readable cached category or series labels.",
            location=location,
        )
    if chart.get(xml_names.XLINK_HREF) not in {None, ".", "./"}:
        report.raise_(
            rules.CHART005,
            "Chart refers to an external data provider; it was not fetched.",
            location=location,
        )


def _ranges(chart: etree._Element, report: Report) -> None:
    selectors = (
        ".//*[@chart:values-cell-range-address or @chart:label-cell-address "
        "or @table:cell-range-address]"
    )
    for index, node in enumerate(select_elements(chart, selectors), 1):
        for attribute in (
            xml_names.CHART_VALUES_CELL_RANGE_ADDRESS,
            xml_names.CHART_LABEL_CELL_ADDRESS,
            xml_names.TABLE_CELL_RANGE_ADDRESS,
        ):
            address = node.get(attribute)
            if address is None:
                continue
            location = Location.indexed(Part.CONTENT, "chart-range", index)
            try:
                shape = range_shape(chart, address)
            except DocumentRefusal as exc:
                report.raise_(rules.CHART004, str(exc), location=location)
                continue
            if shape is None:
                report.raise_(
                    rules.CHART005,
                    "Chart data range cannot be resolved against its local cache.",
                    location=location,
                )
            elif min(shape) > 1:
                report.raise_(
                    rules.CHART006,
                    "A multidimensional series range needs ordering/label review.",
                    location=location,
                )


def _series_consistency(chart: etree._Element, report: Report) -> None:
    for plot in select_elements(chart, "./chart:plot-area"):
        categories = select_elements(plot, "./chart:axis/chart:categories")
        category = (
            _resolved(chart, categories[0].get(xml_names.TABLE_CELL_RANGE_ADDRESS))
            if len(categories) == 1
            else None
        )
        for index, series in enumerate(select_elements(plot, "./chart:series"), 1):
            values = _resolved(chart, series.get(xml_names.CHART_VALUES_CELL_RANGE_ADDRESS))
            if values is None:
                continue
            location = Location.indexed(Part.CONTENT, "chart-series", index)
            if (
                category is not None
                and min(category.shape) == min(values.shape) == 1
                and max(category.shape) != max(values.shape)
            ):
                report.raise_(
                    rules.CHART006,
                    "Cached categories and series values have different logical lengths.",
                    location=location,
                )
            try:
                nonnumeric = False
                for cell in values.cells():
                    if _nonnumeric(cell):
                        nonnumeric = True
            except DocumentRefusal as exc:
                report.raise_(rules.CHART004, str(exc), location=location)
                continue
            if nonnumeric:
                report.raise_(
                    rules.CHART006,
                    "Series includes nonblank cells without a numeric or temporal value type.",
                    location=location,
                )


def _resolved(chart: etree._Element, address: str | None) -> LocalRange | None:
    if address is None:
        return None
    try:
        return resolve_range(chart, address)
    except DocumentRefusal:
        return None  # Range diagnostics are emitted once by _ranges.


def _nonnumeric(cell: etree._Element) -> bool:
    if cell.tag == xml_names.TABLE_COVERED_TABLE_CELL:
        return False
    numeric = {"float", "percentage", "currency", "date", "time"}
    if cell.get(xml_names.OFFICE_VALUE_TYPE) in numeric:
        return False
    has_value = any(
        (cell.get(qn("office", name)) or "").strip()
        for name in ("value", "string-value", "boolean-value")
    )
    return bool(has_value or visible_words(cell))
