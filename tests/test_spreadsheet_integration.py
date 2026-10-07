# SPDX-License-Identifier: MPL-2.0
"""Spreadsheets authored by LibreOffice itself: audited, edited, reloaded, exported and compared."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y.audit import audit_odf
from odfa11y.errors import RemediationError
from odfa11y.external_tools import run_bounded
from odfa11y.families.spreadsheet import ObjectAltText, SetObjectAltText, SetSheetNames
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument
from odfa11y.pdf import ExportSettings, export_pdfua
from odfa11y.pipeline import STAGE_NAMES, PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

from .spreadsheet_fixtures import (
    HIDDEN_SHEET_STYLE,
    data_sheet,
    make_spreadsheet,
    picture,
    row,
    sheet,
    text_cell,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.pipeline import RunRecord

pytestmark = pytest.mark.integration
PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQ"
    "GAhKmMIQAAAABJRU5ErkJggg=="
)
ALT = "<svg:title>Sample</svg:title><svg:desc>A one pixel sample picture</svg:desc>"
LINK = (
    '<text:a xlink:href="https://example.org/a" xlink:type="simple">https://example.org/a</text:a>'
)
REFERENCE = 'table:formula="of:=[$Data.A1]"'


def author(directory: Path, soffice: str, *sheets: str, styles: str = "") -> Path:
    """Have LibreOffice itself write a package from a flat description.

    Returns
    -------
    Path
        An ``.ods`` that LibreOffice saved, not one this repository assembled.

    """
    flat = make_spreadsheet(directory, "flat", *sheets, automatic_styles=styles)
    out = directory / "authored"
    command = [
        soffice,
        f"-env:UserInstallation={(directory / 'profile').as_uri()}",
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        "--nofirststartwizard",
        "--convert-to",
        "ods",
        "--outdir",
        str(out),
        str(flat),
    ]
    result = run_bounded(command, timeout=120)
    output = out / f"{flat.stem}.ods"
    assert result.returncode == 0, result
    assert output.is_file(), result
    return output


def problem_sheets() -> tuple[str, ...]:
    merged = row(
        text_cell("Total", 'table:number-columns-spanned="2"'), "<table:covered-table-cell/>"
    )
    hidden = row(text_cell("Pears"), text_cell("4"), attributes='table:visibility="collapse"')
    return (
        sheet(
            "Sheet1",
            row(text_cell("Item"), text_cell("Amount")),
            row(text_cell("Apples"), text_cell("3")),
            hidden,
            merged,
            row(text_cell("x", REFERENCE), text_cell(LINK)),
            row(picture("Logo", data=PNG), text_cell("after")),
        ),
        sheet("Data", row(text_cell("x")), style="taHidden"),
        sheet("Blank", row("<table:table-cell/>")),
    )


def clean_sheets() -> tuple[str, ...]:
    return (
        sheet(
            "Fruit",
            row(text_cell("Item"), text_cell("Amount")),
            row(text_cell("Apples"), text_cell("3")),
            row(picture("Logo", alt=ALT, data=PNG), text_cell("Pears")),
            header_rows=1,
        ),
    )


def pdf_text(path: Path) -> str:
    return " ".join(page.extract_text() for page in PdfReader(path).pages)


def stages(record: RunRecord) -> dict[str, str]:
    return {stage.name: stage.status for stage in record.stages}


def test_libreoffice_authored_packages_are_recognised_and_audited(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = author(
        tmp_path,
        external_tool("soffice", "libreoffice"),
        *problem_sheets(),
        styles=HIDDEN_SHEET_STYLE,
    )
    document = OdfDocument.open(source)
    assert document.layout == "package"
    assert document.kind is not None
    assert document.kind.family.value == "spreadsheet"
    report = audit_odf(source, schema=True)
    spreadsheet_rules = {f.rule_id for f in report.findings if f.rule_id.startswith("SHEET")}
    assert spreadsheet_rules == {f"SHEET00{n}" for n in (2, 3, 4, 5, 6, 7, 8)}
    hidden = next(f for f in report.findings if f.rule_id == "SHEET008")
    assert hidden.details == {"sheets": ["Data"], "rows": 1, "columns": 0}
    assert report.metadata["adapter"] == "spreadsheet"
    assert report.metadata["sheet_count"] == 3


def test_a_plan_on_a_libreoffice_authored_package_reloads_and_prints_the_new_name(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = author(tmp_path, soffice, *problem_sheets(), styles=HIDDEN_SHEET_STYLE)
    fingerprint = next(
        str(f.details["fingerprint"]) for f in audit_odf(source).findings if f.rule_id == "SHEET005"
    )
    plan = [
        SetSheetNames({"Sheet1": "Fruit prices", "Blank": "Spare"}),
        SetObjectAltText({"Logo": ObjectAltText("Logo", "A sample picture", fingerprint)}),
    ]
    output = tmp_path / "remediated.ods"
    result = remediate(source, output, plan)
    assert result.changed
    after = {f.rule_id for f in audit_odf(output, schema=True).findings}
    assert not {"SHEET002", "SHEET005"} & after
    export = ExportSettings("calc_pdf_Export", soffice, profile_dir=tmp_path / "profile")
    before_text = pdf_text(export_pdfua(source, tmp_path / "source.pdf", export))
    after_text = pdf_text(export_pdfua(output, tmp_path / "remediated.pdf", export))
    assert "Fruit prices" in after_text
    assert "Fruit prices" not in before_text
    assert "Apples" in after_text
    assert not remediate(output, tmp_path / "again.ods", plan).changed


def test_a_sheet_a_libreoffice_formula_refers_to_is_not_renamed(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = author(
        tmp_path,
        external_tool("soffice", "libreoffice"),
        *problem_sheets(),
        styles=HIDDEN_SHEET_STYLE,
    )
    output = tmp_path / "remediated.ods"
    with pytest.raises(RemediationError, match="may refer to it by name"):
        remediate(source, output, [SetSheetNames({"Data": "Notes"})])
    assert not output.exists()


def test_the_pipeline_exports_a_calc_spreadsheet_and_audits_its_pdf(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = author(tmp_path, soffice, *clean_sheets())
    plan = [SetMetadata(language="en-GB")]
    options = PipelineOptions(soffice=soffice)
    record = run_pipeline(source, plan, FidelityPolicy(), tmp_path / "out", options)
    assert stages(record) == dict.fromkeys(STAGE_NAMES, "passed") | {"verapdf": "skipped"}
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["document"]["adapter"] == "spreadsheet"
    assert {"source.pdf", "remediated.pdf", "remediated.ods"} <= set(run["outputs"])
    assert "Apples" in pdf_text(tmp_path / "out" / "remediated.pdf")
    assert "- [ ]" in (tmp_path / "out" / "REVIEW.md").read_text()


def test_renaming_a_sheet_changes_the_printed_header_and_the_fidelity_gate_says_so(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = author(tmp_path, soffice, *clean_sheets())
    plan = [SetSheetNames({"Fruit": "Fruit prices"})]
    record = run_pipeline(
        source, plan, FidelityPolicy(), tmp_path / "out", PipelineOptions(soffice=soffice)
    )
    assert stages(record)["remediate"] == "passed"
    assert stages(record)["fidelity"] == "failed"
    fidelity = next(stage for stage in record.stages if stage.name == "fidelity")
    assert fidelity.report is not None
    assert "FID003" in {f.rule_id for f in fidelity.report.findings}


def test_the_production_profile_runs_veraphdf_on_a_calc_export(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = author(tmp_path, soffice, *clean_sheets())
    options = PipelineOptions(profile="production", soffice=soffice, verapdf_path=verapdf)
    record = run_pipeline(
        source, [SetMetadata(language="en-GB")], FidelityPolicy(), tmp_path / "out", options
    )
    reached = stages(record)
    assert reached["export-source"] == reached["export-remediated"] == "passed"
    assert reached["audit-pdf"] == "passed"
    assert reached["verapdf"] in {"passed", "failed"}
    assert (tmp_path / "out" / "verapdf.xml").is_file()


def test_data_sheets_authored_by_libreoffice_keep_their_header_rows(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = author(
        tmp_path, external_tool("soffice", "libreoffice"), data_sheet("Prices", header_rows=1)
    )
    assert "SHEET003" not in {f.rule_id for f in audit_odf(source).findings}
