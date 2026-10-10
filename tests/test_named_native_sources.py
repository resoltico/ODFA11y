# SPDX-License-Identifier: MPL-2.0
"""Schema-valid named inputs cannot silently bypass the native declaration boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.cli import commands, main
from odfa11y.content import native_export_limitations, require_native_context
from odfa11y.errors import ToolFailedError
from odfa11y.odf import OdfDocument, validate

from .documents import TABLE_BODY, Variant, make_package

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.pdf import ExportSettings

TEXT_FIELDS = ["display", "name", "next", "row-number", "row-select"]
TABLE_SOURCES = {"sql": "sql-statement", "table": "database-table-name", "query": "query-name"}


@pytest.mark.parametrize("field", TEXT_FIELDS)
@pytest.mark.parametrize("binding", ["NamedDatabase", "https://example.test/data.odb", ""])
def test_cached_text_fields_do_not_establish_database_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, binding: str
) -> None:
    column = 'text:column-name="Field"' if field == "display" else ""
    cached = "Cached" if field in {"display", "name", "row-number"} else ""
    body = (
        f'<office:text><text:p><text:database-{field} text:database-name="{binding}" '
        f'text:table-name="Records" {column}>{cached}</text:database-{field}>'
        "</text:p></office:text>"
    )
    source = make_package(tmp_path, "text", Variant(body=body))
    _assert_binding(source, monkeypatch, expected=bool(binding))


@pytest.mark.parametrize("kind", TABLE_SOURCES)
def test_database_imports_are_unestablished_named_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    attribute = TABLE_SOURCES[kind]
    body = (
        "<office:spreadsheet>" + TABLE_BODY + "<table:database-ranges>"
        '<table:database-range table:target-range-address="Sheet1.A1:Sheet1.A1">'
        f'<table:database-source-{kind} table:database-name="NamedDatabase" '
        f'table:{attribute}="Records"/></table:database-range>'
        "</table:database-ranges></office:spreadsheet>"
    )
    source = make_package(tmp_path, "spreadsheet", Variant(body=body))
    _assert_binding(source, monkeypatch, expected=True)


@pytest.mark.parametrize("kind", ["text-dde", "table-dde", "service"])
def test_declared_application_and_service_inputs_are_unestablished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    dde = (
        'office:dde-application="NamedApplication" office:dde-topic="Topic" office:dde-item="Item"'
    )
    if kind == "text-dde":
        body = (
            "<office:text><text:dde-connection-decls>"
            f'<text:dde-connection-decl office:name="Control" {dde}/>'
            "</text:dde-connection-decls><text:p>Cached</text:p></office:text>"
        )
        family = "text"
    elif kind == "table-dde":
        table = TABLE_BODY.replace(
            "<table:table-column/>", f"<office:dde-source {dde}/><table:table-column/>"
        )
        body = "<office:spreadsheet>" + table + "</office:spreadsheet>"
        family = "spreadsheet"
    else:
        body = (
            "<office:spreadsheet>" + TABLE_BODY + "<table:data-pilot-tables>"
            '<table:data-pilot-table table:name="Pilot" '
            'table:target-range-address="Sheet1.A1:Sheet1.A1">'
            '<table:source-service table:name="NamedService" '
            'table:source-name="Source" table:object-name="Object"/>'
            '<table:data-pilot-field table:source-field-name="Field" table:orientation="row"/>'
            "</table:data-pilot-table></table:data-pilot-tables></office:spreadsheet>"
        )
        family = "spreadsheet"
    source = make_package(tmp_path, family, Variant(body=body))
    _assert_binding(source, monkeypatch, expected=True)


def _assert_binding(source: Path, monkeypatch: pytest.MonkeyPatch, *, expected: bool) -> None:
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    count = 1 if expected else 0
    assert native_export_limitations(document)["rendering_dependencies"] == count
    report = audit_odf(source)
    assert ("ODF012" in {f.rule_id for f in report.findings}) == expected
    assert report.metadata["native_export_limitations"]["rendering_dependencies"] == count
    if expected:
        with pytest.raises(ToolFailedError):
            require_native_context(document)

        def refuse_launch(_source: Path, _destination: Path, _settings: ExportSettings) -> Path:
            pytest.fail("named source bypassed preflight and reached native application export")

        monkeypatch.setattr(commands, "export_pdfua", refuse_launch)
        assert (
            main([
                "export",
                str(source),
                str(source.with_suffix(".pdf")),
                "--soffice",
                "must-not-launch",
            ])
            == 3
        )
    else:
        require_native_context(document)
