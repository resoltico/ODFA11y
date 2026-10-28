# SPDX-License-Identifier: MPL-2.0
"""A spreadsheet plan end to end: configuration, the executor's guards, and family boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

import pytest

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import GraphicAlternative
from odfa11y.errors import PlanError
from odfa11y.families.spreadsheet import SetGraphicAlternatives, SetSheetNames
from odfa11y.families.text import SetGraphicAlternatives as TextGraphicAlternatives
from odfa11y.odf import Family, OdfDocument, Part, select_elements
from odfa11y.outcomes import StageStatus
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.plans import load_plan
from odfa11y.remediation import SetMetadata
from odfa11y.remediation.planning import compile_operations
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from odfa11y.tools import Tools

from .operation_execution import assert_refused, execute_operations
from .reviewed_plans import plan_header, reviewed_plan
from .spreadsheet_fixtures import (
    LAYOUTS,
    make_spreadsheet,
    picture,
    reviewed_sheet_names,
    row,
    sheet,
    text_cell,
)

if TYPE_CHECKING:
    from pathlib import Path


by_layout = pytest.mark.parametrize("layout", LAYOUTS)
SHEETS = (
    sheet("Sheet1", row(text_cell("a"), picture("Logo"))),
    sheet("Notes", row(text_cell("b"))),
)


def write_config(directory: Path, text: str) -> Path:
    path = directory / "plan.toml"
    path.write_text(plan_header(directory / "unused") + text, encoding="utf-8")
    return path


def ids(path: Path) -> set[str]:
    return {finding.rule_id for finding in audit_odf(path).findings}


class EditCell(Operation):
    """A test operation that, unlike every shipped one, changes what a sheet shows."""

    name: ClassVar[str] = "edit_cell"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.SPREADSHEET})

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        [paragraph] = select_elements(document.tree(Part.CONTENT), "//table:table[1]//text:p")[:1]
        document.tree(Part.CONTENT)
        paragraph.text = "changed"
        return (Outcome(self.name, Status.APPLIED, "Edited a cell."),)


def test_the_configuration_reads_the_spreadsheet_table_in_canonical_order(tmp_path: Path) -> None:
    source = make_spreadsheet(tmp_path, "package", *SHEETS)
    plan = load_plan(
        write_config(
            tmp_path,
            '[decisions."graphic.alternative"."content/sheet[1]/frame[name=Logo]"]\n'
            'title = "Logo"\nfingerprint = "0123456789abcdef"\n'
            '[decisions."sheet.name"."content/sheet[1]"]\n'
            'name = "Budget"\nfingerprint = "fedcba9876543210"\n',
        )
    )
    first, second = compile_operations(OdfDocument.open(source), plan)
    assert isinstance(first, SetSheetNames)
    assert first.name == "set_sheet_names"
    assert first.entries["content/sheet[1]"].name == "Budget"
    assert first.entries["content/sheet[1]"].fingerprint == "fedcba9876543210"
    assert second == SetGraphicAlternatives({
        "content/sheet[1]/frame[name=Logo]": GraphicAlternative("Logo", None, "0123456789abcdef")
    })


@pytest.mark.parametrize(
    "content",
    [
        '[decisions."sheet.name"]\nsheets = 1',
        '[decisions]\n"sheet.name" = "x"',
        '[decisions."sheet.name"."content/sheet[1]"]\nname = 3',
        '[decisions."sheet.name"."content/sheet[1]"]\nname = ""',
        '[decisions."sheet.name"."content/sheet[1]"]\nname = "a/b"',
        '[decisions."sheet.name"." "]\nname = "Budget"',
        '[decisions."graphic.alternative"]\nLogo = 1',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescription = 7',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescripton = "x"',
    ],
)
def test_an_invalid_spreadsheet_table_is_rejected_naming_the_key(
    tmp_path: Path, content: str
) -> None:
    with pytest.raises(PlanError):
        load_plan(write_config(tmp_path, content))


def test_empty_spreadsheet_tables_request_nothing(tmp_path: Path) -> None:
    plan = load_plan(write_config(tmp_path, '[decisions."sheet.name"]\n'))
    assert plan.decisions == ()


@by_layout
def test_a_plan_renames_sheets_and_describes_pictures_and_is_idempotent(
    tmp_path: Path, layout: str
) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    plan = [
        reviewed_sheet_names(source, {"Sheet1": "Budget"}),
        SetGraphicAlternatives({"Logo": GraphicAlternative("Logo", "The company logo")}),
    ]
    assert {"SHEET002", "GRAPHIC003"} <= ids(source)
    output = tmp_path / f"out{source.suffix}"
    result = execute_operations(source, output, plan)
    assert result.changed
    assert result.schema.status == StageStatus.PASSED
    assert result.schema.new_count == 0
    assert not {"SHEET002", "GRAPHIC003"} & ids(output)
    again = execute_operations(output, tmp_path / f"again{source.suffix}", plan)
    assert not again.changed
    assert {o.status for o in again.outcomes} == {Status.UNCHANGED}


@by_layout
def test_the_language_reaches_the_default_cell_style(tmp_path: Path, layout: str) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / f"out{source.suffix}"
    execute_operations(source, output, [SetMetadata(language="fr-FR")])
    report = audit_odf(output, schema=True)
    assert report.facts[FactKeys.DOCUMENT_LANGUAGE] == "fr-FR"
    assert "META003" not in {f.rule_id for f in report.findings}
    assert "SCHEMA001" not in {f.rule_id for f in report.findings}
    again = execute_operations(
        output, tmp_path / f"again{source.suffix}", [SetMetadata(language="fr-FR")]
    )
    assert not again.changed


@by_layout
def test_a_rename_that_would_break_a_reference_stops_the_run_and_writes_nothing(
    tmp_path: Path, layout: str
) -> None:
    caller = sheet("Calc", row(text_cell("x", 'table:formula="of:=[$Notes.A1]"')))
    source = make_spreadsheet(tmp_path, layout, *SHEETS, caller)
    output = tmp_path / f"out{source.suffix}"
    assert_refused(
        execute_operations(source, output, [reviewed_sheet_names(source, {"Notes": "Memo"})]),
        match="may refer to it by name",
    )
    assert not output.exists()


@by_layout
def test_an_operation_that_changes_what_a_sheet_shows_is_refused(
    tmp_path: Path, layout: str
) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / f"out{source.suffix}"
    assert_refused(execute_operations(source, output, [EditCell()]), match="content changed")
    assert_refused(
        execute_operations(
            source, output, [reviewed_sheet_names(source, {"Sheet1": "Budget"}), EditCell()]
        ),
        match="content changed",
    )
    assert not output.exists()


@by_layout
def test_a_text_plan_is_refused_for_a_spreadsheet(tmp_path: Path, layout: str) -> None:
    source = make_spreadsheet(tmp_path, layout, *SHEETS)
    output = tmp_path / "out"
    assert_refused(
        execute_operations(
            source, output, [TextGraphicAlternatives({"Logo": GraphicAlternative("x")})]
        ),
        match="do not apply to a spreadsheet document",
    )
    assert not output.exists()


@by_layout
def test_a_spreadsheet_plan_is_refused_for_a_text_document(tmp_path: Path, layout: str) -> None:
    source = LAYOUTS[layout](tmp_path, "text")
    output = tmp_path / "out"
    for operation in (
        reviewed_sheet_names(source, {"Sheet1": "Budget"}),
        SetGraphicAlternatives({"Logo": GraphicAlternative("x")}),
    ):
        assert_refused(
            execute_operations(source, output, [operation]), match="do not apply to a text document"
        )
    assert not output.exists()


def test_a_spreadsheet_pipeline_exports_with_the_calc_filter_and_stops_without_libreoffice(
    tmp_path: Path,
) -> None:
    source = make_spreadsheet(tmp_path, "package", *SHEETS)
    options = RunSettings(tools=Tools(soffice=str(tmp_path / "no-such-soffice")))
    plan = [
        reviewed_sheet_names(source, {"Sheet1": "Budget"}),
        SetGraphicAlternatives({"Logo": GraphicAlternative("Logo")}),
    ]
    record = execute(
        source, reviewed_plan(source, plan, FidelityPolicy()), tmp_path / "out", options
    )
    statuses = {stage.name.value: stage.status for stage in record.stages}
    assert statuses["remediate"] == "passed"
    assert statuses["export-source"] == "failed"
    assert statuses["audit-pdf"] == "skipped"
    assert (tmp_path / "out" / "remediated.ods").is_file()
