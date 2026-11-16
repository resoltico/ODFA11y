# SPDX-License-Identifier: MPL-2.0
"""Compose raw native validation with the independent XML interpreter."""

from dataclasses import replace
from pathlib import Path

from odfa11y.native.tools import VeraPdf
from odfa11y.native.verapdf import Validator, run_verapdf
from odfa11y.pdf.validation import (
    MAX_REPORT_BYTES,
    VeraPdfResult,
    add_verapdf_findings,
    parse_validation,
)
from odfa11y.report import Report, ReportKind
from odfa11y.tool_timeout import Timeout


def validate_pdfua(
    pdf: str | Path,
    *,
    tool: VeraPdf,
    timeout: float = Timeout.DEFAULT,
    validator: Validator = run_verapdf,
) -> VeraPdfResult:
    """Interpret one completed invocation without discovering or identifying tools again."""
    output = validator(pdf, tool=tool, timeout=timeout, max_report_bytes=MAX_REPORT_BYTES)
    return replace(parse_validation(output.xml, output.diagnostics), identity=output.identity)


def check_pdfua(
    pdf: str | Path,
    *,
    subject: str,
    tool: VeraPdf,
    timeout: float = Timeout.DEFAULT,
    validator: Validator = run_verapdf,
) -> tuple[Report, VeraPdfResult]:
    """Return findings and parsed XML from the already resolved validator."""
    report = Report(kind=ReportKind.PDF_VALIDATION, subject=subject, _sources=(Path(pdf),))
    result = validate_pdfua(pdf, tool=tool, timeout=timeout, validator=validator)
    add_verapdf_findings(report, result)
    return report, result
