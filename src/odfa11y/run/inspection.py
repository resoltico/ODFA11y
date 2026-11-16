# SPDX-License-Identifier: MPL-2.0
"""Dispatch read-only document inspection and optional PDF/UA validation."""

from pathlib import Path
lazy from collections.abc import Iterator

from odfa11y.application.native import NativeTools
from odfa11y.audit import audit_odf
from odfa11y.audit.validation import check_pdfua
from odfa11y.pdf import audit_pdfua
from odfa11y.progress import ProgressEvent, Step, StepState
from odfa11y.run.comparison import is_pdf
from odfa11y.tool_timeout import Timeout
lazy from odfa11y.progress import ProgressObserver
lazy from odfa11y.report import Report


def audit_document(
    source: str | Path,
    *,
    schema: bool = False,
    verapdf: bool = False,
    verapdf_path: str | Path | None = None,
    timeout: float = Timeout.DEFAULT,
    on_progress: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> Iterator[Report]:
    """Inspect a regular document by content, then optionally validate a PDF.

    Reports are yielded as checks complete. Consume incrementally to retain the built-in
    PDF report if a later validator execution fails. An unavailable validator is a warning
    report, following ``check_pdfua``. ODF schema inspection applies only to ODF inputs.
    The progress observer receives typed ProgressEvent values and must not raise.

    Yields
    ------
    Report
        The ODF or built-in PDF report, followed by a requested veraPDF report for PDFs.

    """
    native_tools = native_tools or NativeTools()
    timeout = Timeout(timeout)
    source = Path(source)
    if on_progress is not None:
        on_progress(ProgressEvent(Step.AUDIT_DOCUMENT, StepState.RUNNING))
    if not is_pdf(source):
        yield audit_odf(source, schema=schema)
        return
    yield audit_pdfua(source)
    if verapdf or verapdf_path:
        if on_progress is not None:
            on_progress(ProgressEvent(Step.VALIDATE_PDF, StepState.RUNNING))
        report, _result = check_pdfua(
            source,
            subject=str(source),
            executable=verapdf_path,
            timeout=timeout,
            validator=native_tools.validate,
            locate=native_tools.validator,
        )
        yield report
