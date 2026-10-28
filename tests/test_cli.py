# SPDX-License-Identifier: MPL-2.0
"""Command behaviour: output formats, exit statuses and failures without tracebacks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main

from .fixtures import make_minimal_odt
from .pdf_fixtures import tagged_writer, text_pdf
from .reviewed_plans import plan_header

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FINDINGS = 2
EXECUTION_FAILURE = 3
CONFIG = (
    '[decisions."document.metadata"]\n'
    'title = "Updated"\n'
    '[decisions."text.linkify_addresses"]\n'
    "enabled = true\n"
)


def config(tmp_path: Path, text: str = CONFIG) -> Path:
    """Write a configuration file.

    Returns
    -------
    Path
        The file path.

    """
    path = tmp_path / "odfa11y.toml"
    path.write_text(plan_header(tmp_path / "a.odt") + text, encoding="utf-8")
    return path


def test_audit_prints_json_for_one_file_and_an_array_for_several(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = make_minimal_odt(tmp_path / "a.odt")
    second = make_minimal_odt(tmp_path / "b.odt")
    assert main(["audit", str(first), "--format", "json"]) == 0
    one = json.loads(capsys.readouterr().out)
    assert (one["kind"], one["passed"], one["facts"]["document.title"]) == (
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
    failing = make_minimal_odt(tmp_path / "bad.odt", features={"with_image_without_alt": True})
    assert main(["audit", str(failing)]) == FINDINGS
    output = capsys.readouterr().out
    assert "Check: errors found" in output
    assert "graphic.alternative" in output
    warned = make_minimal_odt(tmp_path / "warn.odt", features={"with_plain_email": True})
    assert main(["audit", str(warned)]) == 0
    assert main(["audit", str(warned), "--strict"]) == 1


def test_audit_with_schema_flag_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["audit", str(source), "--schema", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["facts"]["schema.violation_count"] == 0


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
    source = make_minimal_odt(tmp_path / "a.odt", features={"with_image_without_alt": True})
    assert main(["plan", str(source)]) == 0
    output = capsys.readouterr().out
    assert '# [decisions."graphic.alternative"."content/frame[name=Logo]"]' in output


def test_remediate_reports_each_outcome_and_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt", features={"with_plain_email": True})
    destination = tmp_path / "out.odt"
    arguments = ["remediate", str(source), str(destination), "--plan", str(config(tmp_path))]
    assert main([*arguments, "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "Dry run; proposed changes only. Nothing written." in dry
    assert not destination.exists()
    assert main(arguments) == 0
    output = capsys.readouterr().out
    assert f"Wrote: {destination}" in output
    assert "applied   set_metadata [title]" in output
    assert "Schema: passed; ODF 1.4; 0 before, 0 after, 0 new" in output
    assert destination.is_file()


def test_remediate_json_output_is_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "remediate",
        str(source),
        str(tmp_path / "o.odt"),
        "--plan",
        str(config(tmp_path)),
    ]
    assert main([*arguments, "--format", "json", "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["operations"][0]["operation"] == "set_metadata"
    assert data["outcomes"][0]["status"] == "applied"


def test_remediation_refusals_return_outcomes_with_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    bad = config(
        tmp_path,
        (
            '[decisions."table.headers"."content/table[name=Missing]"]\n'
            "rows = 1\n"
            'fingerprint = "0000000000000000"\n'
        ),
    )
    destination = tmp_path / "out.odt"
    assert main(["remediate", str(source), str(destination), "--plan", str(bad)]) == 2
    assert "must resolve to exactly one table" in capsys.readouterr().out
    assert not destination.exists()


def test_invalid_configuration_is_reported_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    invalid = config(tmp_path, '[decisions."document.metadata"]\nlanguage = 7\n')
    assert main(["remediate", str(source), str(tmp_path / "o.odt"), "--plan", str(invalid)]) == 4
    assert "document.metadata.language has an unsupported value type" in capsys.readouterr().err


def test_removed_flags_and_commands_are_rejected() -> None:
    for arguments in (
        ["remediate", "a", "b", "--plan", "c", "--title", "x"],
        ["normalize-spacing", "a", "b"],
        ["check-evidence", "a"],
        ["styles", "a"],
        ["export-pdfua", "a", "b"],
    ):
        with pytest.raises(SystemExit) as raised:
            main(arguments)
        assert raised.value.code == 4


def test_styles_prints_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["audit", str(source), "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)["facts"]["text.paragraph_styles"]
    assert any(row["style"] == "Body" for row in rows)
    assert main(["audit", str(source)]) == 0
    assert "Paragraph styles:" in capsys.readouterr().out
    assert main(["audit", str(source)]) == 0
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
    assert main(["compare", str(left), str(right), "--plan", str(relaxed)]) == 0


def test_check_evidence_reports_integrity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", str(tmp_path)]) == FINDINGS
    assert "Cannot read manifest.json" in capsys.readouterr().out


def test_missing_input_file_is_an_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["audit", str(tmp_path / "absent.odt")]) == EXECUTION_FAILURE
    assert "error:" in capsys.readouterr().err


def test_pipeline_command_without_libreoffice_fails_with_evidence_and_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "pipeline",
        str(source),
        "--plan",
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
    assert json.loads(capsys.readouterr().out)["facts"]["fidelity.raster_max_changed_ratio"] == 0.0
    assert main(["audit", str(pdf)]) == 0
    capsys.readouterr()
    arguments = ["pipeline", str(source), "--plan", str(config(tmp_path)), "--soffice", soffice]
    assert main([*arguments, "--output-dir", str(tmp_path / "ev")]) == 0
    assert main(["verify", str(tmp_path / "ev")]) == 0


def test_verapdf_flag_does_not_swallow_the_next_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    assert main(["audit", "--verapdf", str(pdf), "--format", "json"]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert [report["kind"] for report in reports] == ["pdf", "verapdf"]
