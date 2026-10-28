# SPDX-License-Identifier: MPL-2.0
"""Calc's declared PDF/UA experiment uses an explicit semantic header row."""

from __future__ import annotations

lazy from pathlib import Path

from odfa11y.native.probe_pdf import calc_pdfua
from odfa11y.native.probe_sources import write_probe_package
from odfa11y.native.probes import CapabilityProbe, ProbeId
from odfa11y.odf import Family


def write_calc_probe(directory: Path) -> Path:
    """Write a small table with explicit header rows and document metadata.

    Returns
    -------
    Path
        The synthetic Calc package.

    """
    header = (
        "<table:table-header-rows><table:table-row><table:table-cell "
        'office:value-type="string"><text:p>Fruit</text:p></table:table-cell>'
        '<table:table-cell office:value-type="string"><text:p>Count</text:p>'
        "</table:table-cell></table:table-row></table:table-header-rows>"
    )
    row = (
        '<table:table-row><table:table-cell office:value-type="string"><text:p>'
        "Apples</text:p></table:table-cell><table:table-cell "
        'office:value-type="float" office:value="3"><text:p>3</text:p>'
        "</table:table-cell></table:table-row>"
    )
    return write_probe_package(
        directory / "table.ods",
        "application/vnd.oasis.opendocument.spreadsheet",
        (
            '<office:spreadsheet><table:table table:name="Fruit">'
            '<table:table-column table:number-columns-repeated="2"/>'
        )
        + header
        + row
        + "</table:table></office:spreadsheet>",
    )


PROBES = (
    CapabilityProbe(
        ProbeId.CALC_PDFUA,
        Family.SPREADSHEET,
        write_calc_probe,
        "calc_pdf_Export",
        calc_pdfua,
        frozenset(),
        (
            "The small semantic Calc table passes strict PDF inspection and "
            "veraPDF PDF/UA-1 validation."
        ),
    ),
)
