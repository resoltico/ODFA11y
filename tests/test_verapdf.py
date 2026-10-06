# SPDX-License-Identifier: MPL-2.0
"""Verify validator subprocess/report handling without claiming real veraPDF conformance."""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

import pytest

from odfa11y.pdf_export import run_verapdf

if TYPE_CHECKING:
    from pathlib import Path


def _validator(directory: Path, xml: str, *, status: int = 0) -> Path:
    if os.name == "nt":
        report = directory / "report.xml"
        report.write_text(xml, encoding="utf-8")
        executable = directory / "validator-stub.cmd"
        executable.write_text(f'@echo off\ntype "{report}"\nexit /b {status}\n', encoding="utf-8")
    else:
        executable = directory / "validator-stub"
        executable.write_text(
            f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(xml)}\nexit {status}\n", encoding="utf-8"
        )
        executable.chmod(0o700)
    return executable


@pytest.mark.parametrize(("compliant", "expected"), [("true", True), ("false", False)])
def test_reported_compliance_is_parsed(tmp_path: Path, compliant: str, *, expected: bool) -> None:
    xml = f'<report><validationReport isCompliant="{compliant}"/></report>'
    executable = _validator(tmp_path, xml)
    result, raw = run_verapdf(tmp_path / "input.pdf", executable=executable)
    assert result is expected
    assert raw.strip() == xml


@pytest.mark.parametrize(
    ("xml", "message"), [("not XML", "parse"), ("<report/>", "no validationReport")]
)
def test_invalid_or_empty_validation_reports_are_rejected(
    tmp_path: Path, xml: str, message: str
) -> None:
    executable = _validator(tmp_path, xml)
    with pytest.raises(RuntimeError, match=message):
        run_verapdf(tmp_path / "input.pdf", executable=executable)


def test_process_failure_without_report_is_rejected(tmp_path: Path) -> None:
    executable = _validator(tmp_path, "", status=1)
    with pytest.raises(RuntimeError, match="veraPDF failed"):
        run_verapdf(tmp_path / "input.pdf", executable=executable)
