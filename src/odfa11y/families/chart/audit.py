# SPDX-License-Identifier: MPL-2.0
"""Audit standalone chart identity, descriptions, cached ranges and labels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import visible_words
from odfa11y.errors import RemediationError
from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import Location, rules

from .ranges import range_shape, resolve_range

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

    from .ranges import LocalRange


def audit_chart(document: OdfDocument, report: Report) -> None:
    """Inspect source semantics without loading external data or inventing an export filter."""
    charts = select_elements(document.tree(Part.CONTENT), "//office:body/office:chart/chart:chart")
    report.metadata["chart_count"] = len(charts)
    location = Location(f"{Part.CONTENT}/chart")
    if len(charts) != 1:
        report.add(rules.CHART001, location=location)
        return
    chart = charts[0]
    if not report.metadata.get("title") and not any(
        visible_words(node) for node in select_elements(chart, "./chart:title")
    ):
        report.add(rules.CHART002, location=location)
    if not report.metadata.get("description"):
        report.add(rules.CHART003, location=Location("meta/description"))
    series = select_elements(chart, "./chart:plot-area/chart:series")
    report.metadata["series_count"] = len(series)
    if not series:
        report.add(rules.CHART001, "The chart declares no data series.", location=location)
    _ranges(chart, report)
    _series_consistency(chart, report)
    labels = select_elements(
        chart,
        "./table:table//table:table-cell[@office:value-type='string']/text:p "
        "| .//chart:title/text:p",
    )
    if not any(visible_words(label) for label in labels):
        report.add(
            rules.CHART006,
            "Chart has no readable cached category or series labels.",
            location=location,
        )
    if chart.get(qn("xlink", "href")) not in {None, ".", "./"}:
        report.add(
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
            qn("chart", "values-cell-range-address"),
            qn("chart", "label-cell-address"),
            qn("table", "cell-range-address"),
        ):
            address = node.get(attribute)
            if address is None:
                continue
            location = Location.indexed(Part.CONTENT, "chart-range", index)
            try:
                shape = range_shape(chart, address)
            except RemediationError as exc:
                report.add(rules.CHART004, str(exc), location=location)
                continue
            if shape is None:
                report.add(
                    rules.CHART005,
                    "Chart data range cannot be resolved against its local cache.",
                    location=location,
                )
            elif min(shape) > 1:
                report.add(
                    rules.CHART006,
                    "A multidimensional series range needs ordering/label review.",
                    location=location,
                )


def _series_consistency(chart: etree._Element, report: Report) -> None:
    for plot in select_elements(chart, "./chart:plot-area"):
        categories = select_elements(plot, "./chart:axis/chart:categories")
        category = (
            _resolved(chart, categories[0].get(qn("table", "cell-range-address")))
            if len(categories) == 1
            else None
        )
        for index, series in enumerate(select_elements(plot, "./chart:series"), 1):
            values = _resolved(chart, series.get(qn("chart", "values-cell-range-address")))
            if values is None:
                continue
            location = Location.indexed(Part.CONTENT, "chart-series", index)
            if (
                category is not None
                and min(category.shape) == min(values.shape) == 1
                and max(category.shape) != max(values.shape)
            ):
                report.add(
                    rules.CHART006,
                    "Cached categories and series values have different logical lengths.",
                    location=location,
                )
            try:
                nonnumeric = False
                for cell in values.cells():
                    if _nonnumeric(cell):
                        nonnumeric = True
            except RemediationError as exc:
                report.add(rules.CHART004, str(exc), location=location)
                continue
            if nonnumeric:
                report.add(
                    rules.CHART006,
                    "Series includes nonblank cells without a numeric or temporal value type.",
                    location=location,
                )


def _resolved(chart: etree._Element, address: str | None) -> LocalRange | None:
    if address is None:
        return None
    try:
        return resolve_range(chart, address)
    except RemediationError:
        return None  # Range diagnostics are emitted once by _ranges.


def _nonnumeric(cell: etree._Element) -> bool:
    if cell.tag == qn("table", "covered-table-cell"):
        return False
    numeric = {"float", "percentage", "currency", "date", "time"}
    if cell.get(qn("office", "value-type")) in numeric:
        return False
    has_value = any(
        (cell.get(qn("office", name)) or "").strip()
        for name in ("value", "string-value", "boolean-value")
    )
    return bool(has_value or visible_words(cell))
