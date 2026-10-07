# SPDX-License-Identifier: MPL-2.0
"""Exercise SARIF through CLI dispatch and real document/PDF boundaries."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from jsonschema import Draft7Validator

from odfa11y.cli import commands, main
from odfa11y.errors import ToolFailedError

from .fixtures import make_minimal_odt
from .pdf_fixtures import tagged_writer, text_pdf
from .test_sarif import SCHEMA

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.pdf import ExportSettings


def _run_log(output: str) -> dict:
    payload = json.loads(output)
    Draft7Validator(
        json.loads(SCHEMA.read_bytes()), format_checker=Draft7Validator.FORMAT_CHECKER
    ).validate(payload)
    return payload["runs"][0]


def test_audit_sarif_mixes_real_odf_pdf_and_verapdf_reports_without_local_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    odf = make_minimal_odt(tmp_path / "document.odt", features={"with_image_without_alt": True})
    pdf = tmp_path / "tagged.pdf"
    tagged_writer().write(pdf)
    arguments = [
        "audit",
        str(odf),
        str(pdf),
        "--format",
        "sarif",
        "--source-root",
        str(tmp_path),
        "--verapdf-path",
        str(tmp_path / "missing-validator"),
    ]
    assert main(arguments) == 2
    output = capsys.readouterr()
    assert not output.err
    assert str(tmp_path) not in output.out
    assert "missing-validator" not in output.out
    run = _run_log(output.out)
    assert run["artifacts"] == [
        {"location": {"uri": "document.odt"}},
        {"location": {"uri": "tagged.pdf"}},
    ]
    by_rule = {result["ruleId"]: result for result in run["results"]}
    assert by_rule["TXT010"]["locations"][0]["physicalLocation"]["artifactLocation"]["index"] == 0
    assert by_rule["VERA000"]["locations"][0]["physicalLocation"]["artifactLocation"]["index"] == 1
    assert by_rule["VERA000"]["level"] == "warning"


def test_compare_odf_sarif_refers_to_original_inputs_after_temporary_pdfs_are_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    generated: list[Path] = []

    def exporter(input_path: Path, destination: Path, _settings: ExportSettings) -> Path:
        assert input_path in {source, candidate}
        generated.append(destination)
        line = "Unchanged" if input_path == source else "Changed"
        return text_pdf(destination, [[line]])

    monkeypatch.setattr(commands, "export_pdfua", exporter)
    assert (
        main([
            "compare",
            str(source),
            str(candidate),
            "--format",
            "sarif",
            "--source-root",
            str(tmp_path),
        ])
        == 2
    )
    output = capsys.readouterr()
    assert not output.err
    assert generated
    assert all(not path.exists() for path in generated)
    assert "odfa11y-compare-" not in output.out
    run = _run_log(output.out)
    assert run["artifacts"] == [
        {"location": {"uri": "candidate.odt"}},
        {"location": {"uri": "source.odt"}},
    ]
    finding = next(result for result in run["results"] if result["ruleId"] == "FID003")
    assert [
        loc["physicalLocation"]["artifactLocation"]["index"] for loc in finding["locations"]
    ] == [0, 1]
    assert "Changed" not in output.out


def test_compare_real_pdfs_has_candidate_then_source_artifact_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = text_pdf(tmp_path / "source.pdf", [["Source sentence"]])
    candidate = text_pdf(tmp_path / "candidate.pdf", [["Candidate sentence"]])
    assert (
        main([
            "compare",
            str(source),
            str(candidate),
            "--format",
            "sarif",
            "--source-root",
            str(tmp_path),
        ])
        == 2
    )
    run = _run_log(capsys.readouterr().out)
    assert run["artifacts"][0]["location"]["uri"] == "candidate.pdf"
    assert run["artifacts"][1]["location"]["uri"] == "source.pdf"
    assert any(result["ruleId"] == "FID003" for result in run["results"])


@pytest.mark.parametrize("suffix", ["odt", "pdf"])
def test_malformed_existing_inputs_still_produce_valid_private_sarif(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], suffix: str
) -> None:
    source = tmp_path / f"malformed.{suffix}"
    source.write_bytes(b"%PDF-invalid" if suffix == "pdf" else b"invalid ZIP document")
    assert (
        main([
            "audit",
            str(source),
            "--format",
            "sarif",
            "--source-root",
            str(tmp_path),
        ])
        == 2
    )
    output = capsys.readouterr()
    run = _run_log(output.out)
    assert run["results"]
    assert str(tmp_path) not in output.out
    assert {item["ruleId"] for item in run["results"]} <= {"PDF000", "PKG000"}


def test_missing_explicit_root_and_outside_sources_fail_without_emitting_partial_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    root = tmp_path / "confined"
    root.mkdir()
    for extra in ([], ["--source-root", str(root)]):
        assert main(["audit", str(source), "--format", "sarif", *extra]) == 3
        output = capsys.readouterr()
        assert not output.out
        assert "error:" in output.err
        assert str(tmp_path) not in output.err


def test_missing_source_fails_without_fake_findings_or_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main([
            "audit",
            str(tmp_path / "missing.odt"),
            "--format",
            "sarif",
            "--source-root",
            str(tmp_path),
        ])
        == 3
    )
    output = capsys.readouterr()
    assert not output.out
    assert "error:" in output.err
    assert "Traceback" not in output.err
    assert str(tmp_path) not in output.err


@pytest.mark.parametrize(
    "arguments",
    [
        ["remediate", "source", "destination", "--config", "plan"],
        ["pipeline", "source", "--config", "plan", "--output-dir", "output"],
        ["batch", "manifest", "--output-dir", "output"],
        ["styles", "source"],
        ["doctor"],
    ],
)
def test_nonreport_commands_reject_sarif_instead_of_printing_other_format(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        main([*arguments, "--format", "sarif"])
    assert exited.value.code == 2
    assert "invalid choice: 'sarif'" in capsys.readouterr().err


def test_sarif_preserves_strict_warning_exit_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warnings.odt", features={"with_plain_email": True})
    arguments = ["audit", str(source), "--format", "sarif", "--source-root", str(tmp_path)]
    assert main(arguments) == 0
    baseline = _run_log(capsys.readouterr().out)
    assert main([*arguments, "--strict"]) == 1
    assert _run_log(capsys.readouterr().out) == baseline


@pytest.mark.parametrize("outside", [False, True])
def test_invalid_sarif_root_is_rejected_before_export_or_diff_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    *,
    outside: bool,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    calls: list[Path] = []

    def exporter(input_path: Path, destination: Path, _settings: ExportSettings) -> Path:
        calls.append(input_path)
        return text_pdf(destination, [["Actual comparison"]])

    monkeypatch.setattr(commands, "export_pdfua", exporter)
    diff = tmp_path / "diff"
    extra: list[str] = []
    if outside:
        root = tmp_path / "confined"
        root.mkdir()
        extra = ["--source-root", str(root)]
    assert (
        main([
            "compare",
            str(source),
            str(candidate),
            "--format",
            "sarif",
            "--diff-dir",
            str(diff),
            *extra,
        ])
        == 3
    )
    assert not calls
    assert not diff.exists()
    assert not capsys.readouterr().out


def test_sarif_tool_failure_omits_private_diagnostics_but_text_keeps_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    diagnostic = f"{tmp_path}/private credentials=unpublishable"

    def exporter(_input: Path, _destination: Path, _settings: ExportSettings) -> Path:
        message = "Conversion failed"
        raise ToolFailedError(message, details=diagnostic)

    monkeypatch.setattr(commands, "export_pdfua", exporter)
    arguments = ["compare", str(source), str(candidate)]
    assert main([*arguments, "--format", "sarif", "--source-root", str(tmp_path)]) == 3
    sarif_output = capsys.readouterr()
    assert not sarif_output.out
    assert "unpublishable" not in sarif_output.err
    assert str(tmp_path) not in sarif_output.err
    assert main(arguments) == 3
    assert diagnostic in capsys.readouterr().err
