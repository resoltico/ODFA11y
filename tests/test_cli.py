# SPDX-License-Identifier: MPL-2.0
"""Preserve CLI output and error behavior across command-module splits."""

from __future__ import annotations

import json
import runpy
import sys
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter

from odfa11y import __version__
from odfa11y.cli import main

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


FINDINGS = 2
EXECUTION_FAILURE = 3


def test_audit_prints_json_and_returns_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    assert main(["audit", str(source), "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["metadata"]["title"] == "Synthetic accessible document"


def test_remediation_prints_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    assert main(["remediate", str(source), str(destination), "--title", "Updated"]) == 0
    assert destination.is_file()
    output = capsys.readouterr().out
    assert str(destination) in output
    assert "Set document title metadata." in output


def test_verify_combines_reports_as_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    assert main(["verify", str(source), "--format", "json"]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert len(reports) == 1
    assert reports[0]["passed"] is True


def test_styles_prints_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    assert main(["styles", str(source), "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert any(row["style"] == "Body" for row in rows)


def test_invalid_configuration_is_reported_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    config = tmp_path / "invalid.toml"
    config.write_text("[document]\nlanguage = 7\n", encoding="utf-8")
    destination = tmp_path / "out.odt"
    assert (
        main(["remediate", str(source), str(destination), "--config", str(config)])
        == EXECUTION_FAILURE
    )
    assert "document.language must be str" in capsys.readouterr().err
    assert not destination.exists()


@pytest.mark.parametrize("strict", [False, True])
def test_pipeline_blocks_failed_source_audit_before_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    strict: bool,
) -> None:
    source = make_minimal_odt(
        tmp_path / "source.odt", with_image_without_alt=not strict, with_plain_email=strict
    )
    destination = tmp_path / "out.odt"
    pdf = tmp_path / "out.pdf"

    def unexpected_export(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Export must not run after the source gate fails")

    monkeypatch.setattr("odfa11y.cli.commands.export_pdfua", unexpected_export)
    arguments = ["pipeline", str(source), str(destination), "--pdf", str(pdf), "--format", "json"]
    if strict:
        arguments.append("--strict")
    expected = 1 if strict else FINDINGS
    assert main(arguments) == expected
    assert destination.is_file()
    assert not pdf.exists()
    reports = json.loads(capsys.readouterr().out)
    assert len(reports) == 1


def test_export_executable_error_is_reported_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    executable = tmp_path / "not-executable"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o600)
    assert (
        main(["export-pdfua", str(source), str(tmp_path / "out.pdf"), "--soffice", str(executable)])
        == EXECUTION_FAILURE
    )
    assert "error:" in capsys.readouterr().err


def test_text_audit_prints_a_readable_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_image_without_alt=True)
    assert main(["audit", str(source)]) == FINDINGS
    output = capsys.readouterr().out
    assert "Result: FAIL" in output
    assert "IMG001" in output


def test_doctor_reports_installed_versions(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--format", "json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["odfa11y"] == __version__
    assert {"python", "lxml", "pypdf"} <= info.keys()


def test_module_entry_point_runs_the_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["odfa11y", "doctor", "--format", "json"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("odfa11y", run_name="__main__")
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["odfa11y"] == __version__


def test_normalize_spacing_writes_a_copy_with_reference_spacing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    arguments = ["normalize-spacing", str(source), str(destination)]
    arguments += ["--reference-text", "Body paragraph.", "--target-style", "Body"]
    assert main(arguments) == 0
    assert destination.is_file()
    assert f"Wrote: {destination}" in capsys.readouterr().out


def test_verify_pdf_reports_inspection_errors_for_an_untagged_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / "untagged.pdf"
    writer.write(pdf)
    assert main(["verify-pdf", str(pdf), "--format", "json"]) == FINDINGS
    report = json.loads(capsys.readouterr().out)
    assert {"PDF001", "PDF003", "PDF004"} <= {issue["rule_id"] for issue in report["issues"]}


def test_missing_verapdf_is_a_warning_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / "untagged.pdf"
    writer.write(pdf)
    missing = str(tmp_path / "no-such-verapdf")
    assert main(["verify-pdf", str(pdf), "--verapdf", missing, "--format", "json"]) == FINDINGS
    report = json.loads(capsys.readouterr().out)
    assert "VERA000" in {issue["rule_id"] for issue in report["issues"]}


def test_table_header_and_alt_map_options_override_configuration(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "source.odt", with_data_table=True, with_image_without_alt=True
    )
    alt_map = tmp_path / "alt.json"
    alt_map.write_text(json.dumps({"Logo": {"title": "Logo", "description": "Sample logo"}}))
    destination = tmp_path / "out.odt"
    arguments = ["remediate", str(source), str(destination), "--table-header", "Data=1"]
    arguments += ["--alt-map", str(alt_map)]
    assert main(arguments) == 0
    assert main(["audit", str(destination), "--format", "json"]) == 0


@pytest.mark.parametrize(
    ("option", "message"),
    [
        (["--table-header", "Data"], "expected TABLE=ROWS"),
        (["--table-header", "Data=x"], "expected TABLE=ROWS"),
    ],
)
def test_invalid_table_header_option_is_reported_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], option: list[str], message: str
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    assert main(["remediate", str(source), str(tmp_path / "out.odt"), *option]) == EXECUTION_FAILURE
    assert message in capsys.readouterr().err


def test_alt_map_must_be_a_json_object(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    alt_map = tmp_path / "alt.json"
    alt_map.write_text("[]")
    arguments = ["remediate", str(source), str(tmp_path / "out.odt"), "--alt-map", str(alt_map)]
    assert main(arguments) == EXECUTION_FAILURE
    assert "must be an object" in capsys.readouterr().err
