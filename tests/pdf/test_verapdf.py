# SPDX-License-Identifier: MPL-2.0
"""Validator process and report handling with stub executables (no real veraPDF needed)."""

import os
import shlex
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.errors import ToolFailure, ToolUnavailable
from odfa11y.native.verapdf import find_verapdf
from odfa11y.pdf import add_verapdf_findings
from odfa11y.pdf.validation import ValidationMeasurements, parse_validation
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rule_catalogue
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native import validate_pdfua
from tests.fixtures.verapdf import FAILED_RULE, REPORT


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
    assert failure.contexts == ("root/a", "root/b", "root/c", "root/d")
    assert failure.messages == ("one", "two", "three", "four")
    report = Report(kind=ReportKind.PDF_VALIDATION, subject="in.pdf")
    add_verapdf_findings(report, result)
    finding = report.findings[0]
    assert finding.rule_id == rule_catalogue.PDFUA001.id
    assert "clause 7.1 test 10" in finding.message
    assert finding.details["failed_checks"] == 4
    assert measured(measurement(report, ValidationMeasurements).identity).compliant is False


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
    with pytest.raises(ToolFailure, match=message):
        validate_pdfua(tmp_path / "in.pdf", executable=stub(tmp_path, output, status=status))


def test_missing_validator_is_a_not_found_error(tmp_path: Path) -> None:
    with pytest.raises(ToolUnavailable):
        find_verapdf(tmp_path / "absent")


@pytest.mark.parametrize("namespace", ["default", "prefixed"])
def test_namespaced_report_elements_keep_failure_details(namespace: str) -> None:
    source = report_xml(compliant=False)
    uri = "urn:verapdf:report"
    if namespace == "default":
        xml = source.replace("<report>", f'<report xmlns="{uri}">').encode()
    else:
        root = etree.fromstring(source.encode())
        for node in root.iter():
            node.tag = f"{{{uri}}}{node.tag}"
        xml = etree.tostring(root)
        assert b"<ns0:" in xml
    result = parse_validation(xml)
    assert not result.compliant
    assert result.identity.version == "9.9.9"
    assert result.failures[0].description == "The catalog shall include DisplayDocTitle."
    assert result.failures[0].contexts[0] == "root/a"
    assert result.failures[0].messages[0] == "one"


@pytest.mark.parametrize("value", ["no", "", "-1", "1.5", "\u0661"])
def test_malformed_failed_check_count_is_a_tool_failure(value: str) -> None:
    xml = report_xml(compliant=False).replace('failedChecks="4"', f'failedChecks="{value}"')
    with pytest.raises(ToolFailure, match="malformed failedChecks"):
        parse_validation(xml.encode())


def test_malformed_compliance_boolean_is_a_tool_failure() -> None:
    xml = report_xml(compliant=True).replace('isCompliant="true"', 'isCompliant="perhaps"')
    with pytest.raises(ToolFailure, match="malformed isCompliant"):
        parse_validation(xml.encode())


def test_native_report_bytes_are_not_repaired_before_xml_validation(tmp_path: Path) -> None:
    body = REPORT.format(status="normal", compliant="true", failed=0, rules="").encode()
    body = body.replace(b"</report>", b"<unused>\xff</unused></report>")
    payload = tmp_path / "raw-report.xml"
    payload.write_bytes(body)
    executable = stub(tmp_path, "placeholder")
    executable.write_text(
        f'@echo off\r\ntype "{payload}"\r\n'
        if os.name == "nt"
        else "#!/bin/sh\ncat " + shlex.quote(str(payload)) + "\n"
    )
    with pytest.raises(ToolFailure, match="parse the veraPDF report as XML"):
        validate_pdfua(tmp_path / "input.pdf", executable=executable)


@pytest.mark.parametrize(
    ("compliant", "failed", "rules"),
    [("false", 1, ""), ("false", 0, ""), ("true", 1, FAILED_RULE), ("false", 2, FAILED_RULE)],
)
def test_verdict_counts_and_failed_rule_details_must_agree(compliant, failed, rules) -> None:
    xml = REPORT.format(status="normal", compliant=compliant, failed=failed, rules=rules)
    with pytest.raises(ToolFailure, match="inconsistent"):
        parse_validation(xml.encode())


@pytest.mark.parametrize("value", ["no", "", "-1", "1.5", "\u0661"])
def test_failed_rule_count_is_validated(value: str) -> None:
    xml = REPORT.format(status="normal", compliant="false", failed=value, rules=FAILED_RULE)
    with pytest.raises(ToolFailure, match="malformed failedRules"):
        parse_validation(xml.encode())
