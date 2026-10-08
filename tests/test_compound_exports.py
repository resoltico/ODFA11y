# SPDX-License-Identifier: MPL-2.0
"""Native compound documents retain reviewed semantics and exporter failure controls."""

from __future__ import annotations

from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.content import table_fingerprint
from odfa11y.errors import RemediationError
from odfa11y.external_tools import run_bounded
from odfa11y.families.spreadsheet import SetSheetNames
from odfa11y.families.text import MarkTableHeaders, TableHeaders
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.fidelity.snapshot import read_snapshot
from odfa11y.odf import NS, OdfDocument, Part, qn, select_elements, validate
from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua
from odfa11y.remediation import SetMetadata, remediate

from .documents import Variant, make_flat
from .spreadsheet_fixtures import picture, row, sheet, text_cell
from .test_spreadsheet_integration import ALT, PNG, REFERENCE, author, validation_failures

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration

CELL = '<table:table-cell office:value-type="string"><text:p>Label</text:p>{}</table:table-cell>'
TABLE = (
    '<table:table table:name="{}"><table:table-column/>'
    "<table:table-row>{}</table:table-row><table:table-row>"
    + CELL.format("")
    + "</table:table-row></table:table>"
)
GRAPHIC = (
    '<text:p><draw:frame draw:name="Logo" text:anchor-type="paragraph" '
    'svg:width="1cm" svg:height="1cm">'
    "<draw:image><office:binary-data>"
    + PNG
    + "</office:binary-data></draw:image>"
    + ALT
    + "</draw:frame></text:p>"
)
LINK = (
    '<text:p><text:a xlink:href="https://example.test/compound" xlink:type="simple" '
    'office:name="Compound reference">Compound reference</text:a></text:p>'
)


def test_writer_nested_headers_graphic_and_named_link(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    flat = make_flat(
        tmp_path,
        "text",
        Variant(
            body='<office:text><text:h text:outline-level="1">Compound</text:h>'
            + TABLE.format("Outer", CELL.format(TABLE.format("Inner", CELL.format(""))))
            + GRAPHIC
            + LINK
            + "</office:text>"
        ),
    )
    native = tmp_path / "native"
    result = run_bounded(
        [
            soffice,
            f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}",
            "--headless",
            "--convert-to",
            "odt",
            "--outdir",
            str(native),
            str(flat),
        ],
        timeout=120,
    )
    source = native / f"{flat.stem}.odt"
    assert result.returncode == 0, result
    assert source.is_file(), result
    before = OdfDocument.open(source)
    tables = select_elements(before.tree(Part.CONTENT), "//table:table")
    assert len(tables) == 2
    decisions = {
        str(table.get(qn("table", "name"))): TableHeaders(
            columns=1, fingerprint=table_fingerprint(table)
        )
        for table in tables
    }
    plan = [MarkTableHeaders(decisions), SetMetadata(title="Compound Writer", language="en-GB")]
    output = tmp_path / "edited.odt"
    remediate(source, output, plan)
    assert validate(OdfDocument.open(output)).count == validate(before).count
    assert not remediate(output, tmp_path / "again.odt", plan).changed
    assert not {"TXT021", "TXT022"} & {f.rule_id for f in audit_odf(output).findings}
    pdf = export_pdfua(
        output, tmp_path / "writer.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    report = audit_pdfua(pdf)
    assert report.metadata["structure_tags"].get("TH", 0) == 0
    assert "PDF015" in {f.rule_id for f in report.findings}
    assert not {"PDF000", "PDF007", "PDF010", "PDF019", "PDF023"} & {
        f.rule_id for f in report.findings
    }
    assert validate_pdfua(pdf, executable=external_tool("verapdf")).compliant
    _assert_fidelity(source, pdf, "writer_pdf_Export", soffice)
    _resources_preserved(source, output)
    # Independently alter protected table wording after review; the stale decision rejects it.
    table = select_elements(before.tree(Part.CONTENT), "//table:table")[0]
    paragraph = select_elements(table, ".//text:p")[0]
    paragraph.text = "Changed protected label"
    snapshot = etree.tostring(before.tree(Part.CONTENT))
    assert MarkTableHeaders(decisions).apply(before)[0].status.value == "failed"
    assert etree.tostring(before.tree(Part.CONTENT)) == snapshot


def test_calc_formula_graphic_and_printed_header(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = author(
        tmp_path,
        soffice,
        sheet(
            "Fruit",
            row(text_cell("Item"), text_cell("Amount")),
            row(text_cell("x", REFERENCE), text_cell("3")),
            row(picture("Logo", alt=ALT, data=PNG), text_cell("Pears")),
            header_rows=1,
        ),
        sheet(
            "Data",
            row(text_cell("Apples"), text_cell("4")),
            row(text_cell("Pears"), text_cell("5")),
            header_rows=1,
        ),
    )
    before = OdfDocument.open(source)
    formulas = [
        cell.get(qn("table", "formula"))
        for cell in select_elements(before.tree(Part.CONTENT), "//table:table-cell[@table:formula]")
    ]
    assert formulas
    output = tmp_path / "edited.ods"
    plan = [SetMetadata(title="Compound Calc", language="en-GB")]
    remediate(source, output, plan)
    after = OdfDocument.open(output)
    assert validate(after).count == validate(before).count
    _resources_preserved(source, output)
    assert [
        cell.get(qn("table", "formula"))
        for cell in select_elements(after.tree(Part.CONTENT), "//table:table-cell[@table:formula]")
    ] == formulas
    assert not remediate(output, tmp_path / "again.ods", plan).changed
    pdf = export_pdfua(output, tmp_path / "calc.pdf", ExportSettings("calc_pdf_Export", soffice))
    report = audit_pdfua(pdf)
    assert {f.rule_id for f in report.findings} == {"PDF008", "PDF015"}
    assert validation_failures(pdf, external_tool("verapdf")) == {("7.2", "43")}
    assert "Fruit" in read_snapshot(pdf).text
    _assert_fidelity(source, pdf, "calc_pdf_Export", soffice)
    with pytest.raises(RemediationError, match="may refer to it by name"):
        remediate(source, tmp_path / "rejected.ods", [SetSheetNames({"Data": "Other"})])


def _resources_preserved(source: Path, output: Path) -> None:
    with ZipFile(source) as before, ZipFile(output) as after:
        images = [name for name in before.namelist() if name.startswith("Pictures/")]
        assert images
        assert {name: before.read(name) for name in images} == {
            name: after.read(name) for name in images
        }
    for expression in ("//draw:image/@xlink:href", "//text:a/@xlink:href"):
        assert OdfDocument.open(source).tree(Part.CONTENT).xpath(
            expression, namespaces=NS
        ) == OdfDocument.open(output).tree(Part.CONTENT).xpath(expression, namespaces=NS)


def _assert_fidelity(source: Path, pdf: Path, pdf_filter: str, soffice: str) -> None:
    baseline = export_pdfua(
        source, pdf.with_name("source-" + pdf.name), ExportSettings(pdf_filter, soffice)
    )
    assert compare_pdfs(baseline, pdf, FidelityPolicy()).passed
