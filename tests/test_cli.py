# SPDX-License-Identifier: MPL-2.0
"""Command behaviour: output formats, exit statuses and failures without tracebacks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main

from .fixtures import make_minimal_odt
from .pdf_fixtures import tagged_writer, text_pdf

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FINDINGS = 2
EXECUTION_FAILURE = 3
CONFIG = '[document]\ntitle = "Updated"\n[text.remediation]\nlinkify_plain_addresses = true\n'


def config(tmp_path: Path, text: str = CONFIG) -> Path:
    """Write a configuration file.

    Returns
    -------
    Path
        The file path.

    """
    path = tmp_path / "odfa11y.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_audit_prints_json_for_one_file_and_an_array_for_several(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = make_minimal_odt(tmp_path / "a.odt")
    second = make_minimal_odt(tmp_path / "b.odt")
    assert main(["audit", str(first), "--format", "json"]) == 0
    one = json.loads(capsys.readouterr().out)
    assert (one["kind"], one["passed"], one["metadata"]["title"]) == (
        "odf",
        True,
        "Synthetic accessible document",
    )
    assert main(["audit", str(first), str(second), "--format", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == FINDINGS


def test_audit_dispatches_on_file_content_and_mixes_kinds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    odt = make_minimal_odt(tmp_path / "a.odt")
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    assert main(["audit", str(odt), str(pdf), "--format", "json"]) == 0
    assert [report["kind"] for report in json.loads(capsys.readouterr().out)] == ["odf", "pdf"]


def test_audit_text_exit_status_and_strict_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failing = make_minimal_odt(tmp_path / "bad.odt", with_image_without_alt=True)
    assert main(["audit", str(failing)]) == FINDINGS
    output = capsys.readouterr().out
    assert "Result: FAIL" in output
    assert "remedy: text.alt_text" in output
    warned = make_minimal_odt(tmp_path / "warn.odt", with_plain_email=True)
    assert main(["audit", str(warned)]) == 0
    assert main(["audit", str(warned), "--strict"]) == 1


def test_audit_with_schema_flag_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["audit", str(source), "--schema", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["metadata"]["schema_violations"] == 0


def test_missing_verapdf_is_a_warning_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    arguments = ["audit", str(pdf), "--verapdf-path", str(tmp_path / "absent"), "--format", "json"]
    assert main(arguments) == 0
    reports = json.loads(capsys.readouterr().out)
    assert reports[1]["kind"] == "verapdf"
    assert reports[1]["findings"][0]["rule_id"] == "VERA000"
    assert main([*arguments, "--strict"]) == 1


def test_template_prints_a_loadable_commented_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt", with_image_without_alt=True)
    assert main(["template", str(source)]) == 0
    output = capsys.readouterr().out
    assert '# [text.alt_text."Logo"]' in output


def test_remediate_reports_each_outcome_and_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt", with_plain_email=True)
    destination = tmp_path / "out.odt"
    arguments = ["remediate", str(source), str(destination), "--config", str(config(tmp_path))]
    assert main([*arguments, "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "Dry run; nothing written." in dry
    assert not destination.exists()
    assert main(arguments) == 0
    output = capsys.readouterr().out
    assert f"Wrote: {destination}" in output
    assert "applied   set_metadata [title]" in output
    assert "Schema: no new violations" in output
    assert destination.is_file()


def test_remediate_json_output_is_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "remediate",
        str(source),
        str(tmp_path / "o.odt"),
        "--config",
        str(config(tmp_path)),
    ]
    assert main([*arguments, "--format", "json", "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["operations"][0]["operation"] == "set_metadata"
    assert data["outcomes"][0]["status"] == "applied"


def test_remediation_failures_are_reported_on_stderr_with_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    bad = config(tmp_path, "[text.table_headers]\nMissing = 1\n")
    destination = tmp_path / "out.odt"
    assert (
        main(["remediate", str(source), str(destination), "--config", str(bad)])
        == EXECUTION_FAILURE
    )
    assert "No table is named 'Missing'" in capsys.readouterr().err
    assert not destination.exists()


def test_invalid_configuration_is_reported_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    invalid = config(tmp_path, "[document]\nlanguage = 7\n")
    assert (
        main(["remediate", str(source), str(tmp_path / "o.odt"), "--config", str(invalid)])
        == EXECUTION_FAILURE
    )
    assert "document.language must be str" in capsys.readouterr().err


def test_removed_flags_and_commands_are_rejected() -> None:
    for arguments in (
        ["remediate", "a", "b", "--config", "c", "--title", "x"],
        ["normalize-spacing", "a", "b"],
        ["verify", "a"],
        ["export-pdfua", "a", "b"],
    ):
        with pytest.raises(SystemExit) as raised:
            main(arguments)
        assert raised.value.code == FINDINGS


def test_styles_prints_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["styles", str(source), "--format", "json"]) == 0
    assert any(row["style"] == "Body" for row in json.loads(capsys.readouterr().out))
    assert main(["styles", str(source)]) == 0
    assert "- Body:" in capsys.readouterr().out


def test_compare_pdfs_directly_gates_on_the_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = [["A line of text", "Another line"]]
    left = text_pdf(tmp_path / "a.pdf", lines, top=180)
    right = text_pdf(tmp_path / "b.pdf", lines, top=140)
    assert main(["compare", str(left), str(left), "--format", "json"]) == 0
    capsys.readouterr()
    diff = tmp_path / "diff"
    assert main(["compare", str(left), str(right), "--diff-dir", str(diff)]) == FINDINGS
    assert "FID005" in capsys.readouterr().out
    assert any(diff.iterdir())
    relaxed = config(tmp_path, "[fidelity]\nraster_tolerance = 5.0\n")
    assert main(["compare", str(left), str(right), "--config", str(relaxed)]) == 0


def test_check_evidence_reports_integrity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check-evidence", str(tmp_path)]) == FINDINGS
    assert "Cannot read manifest.json" in capsys.readouterr().out


def test_missing_input_file_is_an_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["styles", str(tmp_path / "absent.odt")]) == EXECUTION_FAILURE
    assert "error:" in capsys.readouterr().err


def test_pipeline_command_without_libreoffice_fails_with_evidence_and_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "pipeline",
        str(source),
        "--config",
        str(config(tmp_path)),
        "--soffice",
        str(tmp_path / "none"),
    ]
    assert main([*arguments, "--output-dir", str(tmp_path / "ev")]) == EXECUTION_FAILURE
    output = capsys.readouterr().out
    assert "failed  export-source" in output
    assert (tmp_path / "ev" / "run.json").is_file()
    assert (
        main([*arguments, "--output-dir", str(tmp_path / "ev"), "--format", "json"])
        == EXECUTION_FAILURE
    )


@pytest.mark.integration
def test_export_compare_and_pipeline_with_real_libreoffice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(tmp_path / "a.odt")
    pdf = tmp_path / "a.pdf"
    assert main(["export", str(source), str(pdf), "--soffice", soffice]) == 0
    assert pdf.is_file()
    capsys.readouterr()
    assert (
        main(["compare", str(source), str(source), "--soffice", soffice, "--format", "json"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["metadata"]["raster_max_changed_ratio"] == 0.0
    assert main(["audit", str(pdf)]) == 0
    capsys.readouterr()
    arguments = ["pipeline", str(source), "--config", str(config(tmp_path)), "--soffice", soffice]
    assert main([*arguments, "--output-dir", str(tmp_path / "ev")]) == 0
    assert main(["check-evidence", str(tmp_path / "ev")]) == 0


def test_verapdf_flag_does_not_swallow_the_next_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    assert main(["audit", "--verapdf", str(pdf), "--format", "json"]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert [report["kind"] for report in reports] == ["pdf", "verapdf"]
