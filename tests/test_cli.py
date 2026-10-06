# SPDX-License-Identifier: MPL-2.0
"""Preserve CLI output and error behavior across command-module splits."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


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
    expected = 1 if strict else 2
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
