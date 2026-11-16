# SPDX-License-Identifier: MPL-2.0
"""Compose independent native acquisition and PDF validation interpretation."""

from collections.abc import Callable
from pathlib import Path

from odfa11y.native.verapdf import find_verapdf, run_verapdf
from odfa11y.pdf.validation import (
    MAX_REPORT_BYTES,
    PdfValidator,
    VeraPdfResult,
    add_verapdf_findings,
    parse_validation,
)
from odfa11y.report import Report, ReportKind
from odfa11y.tool_timeout import Timeout


def validate_pdfua(
    pdf: str | Path,
    *,
    executable: str | Path | None = None,
    flavour: str = "ua1",
    timeout: float = Timeout.DEFAULT,
) -> VeraPdfResult:
    output = run_verapdf(
        pdf,
        executable=executable,
        flavour=flavour,
        timeout=timeout,
        max_report_bytes=MAX_REPORT_BYTES,
    )
    return parse_validation(output.xml, output.diagnostics)


def check_pdfua(
    pdf: str | Path,
    *,
    subject: str,
    executable: str | Path | None = None,
    timeout: float = Timeout.DEFAULT,
    validator: PdfValidator | None = None,
    locate: Callable[[str | Path | None], str] | None = None,
) -> tuple[Report, VeraPdfResult]:
    """Validate a PDF and report the outcome, refusing an unavailable validator.

    Returns
    -------
    tuple[Report, VeraPdfResult]
        The PDF validation report and parsed validator result. Tool absence raises
        ToolUnavailable before a validation report is returned.

    """
    timeout = Timeout(timeout)
    report = Report(kind=ReportKind.PDF_VALIDATION, subject=subject, _sources=(Path(pdf),))
    located = (locate or find_verapdf)(executable)
    result = (validator or validate_pdfua)(pdf, executable=located, timeout=timeout)
    add_verapdf_findings(report, result)
    return report, result
