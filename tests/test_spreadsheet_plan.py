# SPDX-License-Identifier: MPL-2.0
"""A spreadsheet plan end to end: configuration, the executor's guards, and family boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

import pytest

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.config import load_config
from odfa11y.content import GraphicDescription
from odfa11y.errors import ConfigError, RemediationError
from odfa11y.families.spreadsheet import SetGraphicDescriptions, SetSheetNames
from odfa11y.families.text import SetGraphicDescriptions as TextGraphicDescriptions
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import Family, Part, select_elements
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

from .spreadsheet_fixtures import LAYOUTS, make_spreadsheet, picture, row, sheet, text_cell

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.odf import OdfDocument

by_layout = pytest.mark.parametrize("layout", LAYOUTS)
SHEETS = (
    sheet("Sheet1", row(text_cell("a"), picture("Logo"))),
    sheet("Notes", row(text_cell("b"))),
)


def write_config(directory: Path, text: str) -> Path:
    path = directory / "plan.toml"
    path.write_text(text, encoding="utf-8")
    return path


def ids(path: Path) -> set[str]:
    return {finding.rule_id for finding in audit_odf(path).findings}


class EditCell(Operation):
    """A test operation that, unlike every shipped one, changes what a sheet shows."""

    name: ClassVar[str] = "edit_cell"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        [paragraph] = select_elements(document.tree(Part.CONTENT), "//table:table[1]//text:p")[:1]
        document.edit(Part.CONTENT)
        paragraph.text = "changed"
        return (Outcome(self.name, Status.APPLIED, "Edited a cell."),)


def test_the_configuration_reads_the_spreadsheet_table_in_canonical_order(tmp_path: Path) -> None:
    config = load_config(
        write_config(
            tmp_path,
            '[spreadsheet.graphics.Logo]\ntitle = "Logo"\nfingerprint = "abc"\n'
            '[spreadsheet.sheet_names]\n"Sheet1" = "Budget"\n',
        )
    )
    first, second = config.operations
    assert first == SetSheetNames({"Sheet1": "Budget"})
    assert second == SetGraphicDescriptions({"Logo": GraphicDescription("Logo", None, "abc")})


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[spreadsheet]\nsheets = 1", "Unknown spreadsheet keys: sheets"),
        ('[spreadsheet]\nsheet_names = "x"', "must be a table"),
        ("[spreadsheet.sheet_names]\nSheet1 = 3", "spreadsheet.sheet_names.Sheet1 must be str"),
        ('[spreadsheet.sheet_names]\nSheet1 = ""', "not a usable sheet name"),
        ('[spreadsheet.sheet_names]\nSheet1 = "a/b"', "not a usable sheet name"),
        ('[spreadsheet.sheet_names]\n" " = "Budget"', "must name an existing sheet"),
        ("[spreadsheet.graphics]\nLogo = 1", "must be a table"),
        ("[spreadsheet.graphics.Logo]\ndescription = 7", "must be str"),
        ('[spreadsheet.graphics.Logo]\ndescripton = "x"', "Unknown spreadsheet.graphics.Logo keys"),
    ],
)
def test_an_invalid_spreadsheet_table_is_rejected_naming_the_key(
    tmp_path: Path, content: str, message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, content))


def test_empty_spreadsheet_tables_request_nothing(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, "[spreadsheet.sheet_names]\n[spreadsheet]\n"))
    assert config.operations == ()


@by_layout
def test_a_plan_renames_sheets_and_describes_pictures_and_is_idempotent(
    tmp_path: Path, layout: str
) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    plan = [
        SetSheetNames({"Sheet1": "Budget"}),
        SetGraphicDescriptions({"Logo": GraphicDescription("Logo", "The company logo")}),
    ]
    assert {"SHEET002", "SHEET005"} <= ids(source)
    output = tmp_path / f"out{source.suffix}"
    result = remediate(source, output, plan)
    assert result.changed
    assert "no new violations" in result.schema_check
    assert not {"SHEET002", "SHEET005"} & ids(output)
    again = remediate(output, tmp_path / f"again{source.suffix}", plan)
    assert not again.changed
    assert {o.status for o in again.outcomes} == {Status.UNCHANGED}


@by_layout
def test_the_language_reaches_the_default_cell_style(tmp_path: Path, layout: str) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / f"out{source.suffix}"
    remediate(source, output, [SetMetadata(language="fr-FR")])
    report = audit_odf(output, schema=True)
    assert report.metadata["language"] == "fr-FR"
    assert "META003" not in {f.rule_id for f in report.findings}
    assert "ODF900" not in {f.rule_id for f in report.findings}
    again = remediate(output, tmp_path / f"again{source.suffix}", [SetMetadata(language="fr-FR")])
    assert not again.changed


@by_layout
def test_a_rename_that_would_break_a_reference_stops_the_run_and_writes_nothing(
    tmp_path: Path, layout: str
) -> None:
    caller = sheet("Calc", row(text_cell("x", 'table:formula="of:=[$Notes.A1]"')))
    source = make_spreadsheet(tmp_path, layout, *SHEETS, caller)
    output = tmp_path / f"out{source.suffix}"
    with pytest.raises(RemediationError, match="may refer to it by name"):
        remediate(source, output, [SetSheetNames({"Notes": "Memo"})])
    assert not output.exists()


@by_layout
def test_an_operation_that_changes_what_a_sheet_shows_is_refused(
    tmp_path: Path, layout: str
) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / f"out{source.suffix}"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(source, output, [EditCell()])
    with pytest.raises(RemediationError, match="content changed"):
        remediate(source, output, [SetSheetNames({"Sheet1": "Budget"}), EditCell()])
    assert not output.exists()


@by_layout
def test_a_text_plan_is_refused_for_a_spreadsheet(tmp_path: Path, layout: str) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / "out"
    with pytest.raises(RemediationError, match="do not apply to a spreadsheet document"):
        remediate(source, output, [TextGraphicDescriptions({"Logo": GraphicDescription("x")})])
    assert not output.exists()


@by_layout
def test_a_spreadsheet_plan_is_refused_for_a_text_document(tmp_path: Path, layout: str) -> None:
    source = LAYOUTS[layout](tmp_path, "text")
    output = tmp_path / "out"
    for operation in (
        SetSheetNames({"Sheet1": "Budget"}),
        SetGraphicDescriptions({"Logo": GraphicDescription("x")}),
    ):
        with pytest.raises(RemediationError, match="do not apply to a text document"):
            remediate(source, output, [operation])
    assert not output.exists()


def test_a_spreadsheet_pipeline_exports_with_the_calc_filter_and_stops_without_libreoffice(
    tmp_path: Path,
) -> None:
    source = make_spreadsheet(tmp_path, "package", *SHEETS)
    options = PipelineOptions(soffice=str(tmp_path / "no-such-soffice"))
    plan = [
        SetSheetNames({"Sheet1": "Budget"}),
        SetGraphicDescriptions({"Logo": GraphicDescription("Logo")}),
    ]
    record = run_pipeline(source, plan, FidelityPolicy(), tmp_path / "out", options)
    statuses = {stage.name: stage.status for stage in record.stages}
    assert statuses["remediate"] == "passed"
    assert statuses["export-source"] == "failed"
    assert statuses["audit-pdf"] == "skipped"
    assert (tmp_path / "out" / "remediated.ods").is_file()
