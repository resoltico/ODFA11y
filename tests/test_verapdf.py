# SPDX-License-Identifier: MPL-2.0
"""Validator process and report handling with stub executables (no real veraPDF needed)."""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError, ToolNotFoundError
from odfa11y.pdf import add_verapdf_findings, find_verapdf, validate_pdfua
from odfa11y.report import Report

if TYPE_CHECKING:
    from pathlib import Path

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<report>
  <buildInformation>
    <releaseDetails id="core" version="9.9.9" buildDate="x"></releaseDetails>
  </buildInformation>
  <jobs><job>
    <validationReport jobEndStatus="{status}" profileName="PDF/UA-1 validation profile"
        isCompliant="{compliant}">
      <details passedRules="1" failedRules="{failed}">
        {rules}
      </details>
    </validationReport>
  </job></jobs>
</report>"""
FAILED_RULE = """<rule specification="ISO 14289-1:2014" clause="7.1" testNumber="10"
    status="failed" failedChecks="4">
  <description>The catalog shall include DisplayDocTitle.</description>
  <check status="failed"><context>root/a</context><errorMessage>one</errorMessage></check>
  <check status="failed"><context>root/b</context><errorMessage>two</errorMessage></check>
  <check status="failed"><context>root/c</context><errorMessage>three</errorMessage></check>
  <check status="failed"><context>root/d</context><errorMessage>four</errorMessage></check>
</rule>
<rule specification="ISO 14289-1:2014" clause="6.2" testNumber="1" status="passed"
    failedChecks="0"><description>Fine.</description></rule>"""


def stub(directory: Path, output: str, *, status: int = 0) -> Path:
    """Create an executable that prints fixed output and exits with a status.

    Returns
    -------
    Path
        The executable.

    """
    if os.name == "nt":
        body = directory / "body.xml"
        body.write_text(output, encoding="utf-8")
        executable = directory / "validator-stub.cmd"
        executable.write_text(f'@echo off\ntype "{body}"\nexit /b {status}\n', encoding="utf-8")
    else:
        executable = directory / "validator-stub"
        executable.write_text(
            f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(output)}\nexit {status}\n", encoding="utf-8"
        )
        executable.chmod(0o700)
    return executable


def report_xml(*, compliant: bool, status: str = "normal") -> str:
    """Build a veraPDF-style report.

    Returns
    -------
    str
        The XML text.

    """
    rules = "" if compliant else FAILED_RULE
    return REPORT.format(
        status=status, compliant=str(compliant).lower(), failed=0 if compliant else 1, rules=rules
    )


def test_compliant_report_is_parsed_with_identity(tmp_path: Path) -> None:
    result = validate_pdfua(
        tmp_path / "in.pdf", executable=stub(tmp_path, report_xml(compliant=True))
    )
    assert result.compliant
    assert result.failures == ()
    assert (result.identity.name, result.identity.version) == ("veraPDF", "9.9.9")
    assert result.profile == "PDF/UA-1 validation profile"


def test_failed_rules_keep_their_standard_identity_and_sample_contexts(tmp_path: Path) -> None:
    executable = stub(tmp_path, report_xml(compliant=False), status=1)
    result = validate_pdfua(tmp_path / "in.pdf", executable=executable)
    assert not result.compliant
    (failure,) = result.failures
    assert (failure.specification, failure.clause, failure.test_number) == (
        "ISO 14289-1:2014",
        "7.1",
        "10",
    )
    assert failure.failed_checks == 4
    assert failure.contexts == ("root/a", "root/b", "root/c")
    assert failure.messages == ("one", "two", "three")
    report = Report(kind="verapdf", subject="in.pdf")
    add_verapdf_findings(report, result)
    finding = report.findings[0]
    assert finding.rule_id == "VERA001"
    assert "clause 7.1 test 10" in finding.message
    assert finding.details["failed_checks"] == 4
    assert report.metadata["veraPDF"]["compliant"] is False


def test_a_report_is_the_outcome_whatever_the_exit_status(tmp_path: Path) -> None:
    assert validate_pdfua(
        tmp_path / "in.pdf", executable=stub(tmp_path, report_xml(compliant=True), status=7)
    ).compliant


@pytest.mark.parametrize(
    ("output", "status", "message"),
    [
        ("not XML", 0, "parse"),
        ("<report/>", 0, "no validationReport"),
        (report_xml(compliant=True, status="failed to parse"), 0, "could not process"),
        ("", 1, "veraPDF failed"),
    ],
)
def test_execution_and_report_failures_are_distinct_from_non_compliance(
    tmp_path: Path, output: str, status: int, message: str
) -> None:
    with pytest.raises(ToolFailedError, match=message):
        validate_pdfua(tmp_path / "in.pdf", executable=stub(tmp_path, output, status=status))


def test_missing_validator_is_a_not_found_error(tmp_path: Path) -> None:
    with pytest.raises(ToolNotFoundError):
        find_verapdf(tmp_path / "absent")
