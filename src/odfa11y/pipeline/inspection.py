# SPDX-License-Identifier: MPL-2.0
"""Dispatch read-only document inspection and optional PDF/UA validation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odf
from odfa11y.external_tools import validate_timeout
from odfa11y.pdf import DEFAULT_TIMEOUT_SECONDS, audit_pdfua, check_pdfua

from .comparison import is_pdf

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from odfa11y.report import Report


def audit_document(
    source: str | Path,
    *,
    schema: bool = False,
    verapdf: bool = False,
    verapdf_path: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    on_progress: Callable[[str, str], None] | None = None,
) -> Iterator[Report]:
    """Inspect a regular document by content, then optionally validate a PDF.

    Reports are yielded as checks complete. Consume incrementally to retain the built-in
    PDF report if a later validator execution fails. An unavailable validator is a warning
    report, following ``check_pdfua``. ODF schema inspection applies only to ODF inputs.
    The progress observer receives fixed labels/statuses and must not raise.

    Yields
    ------
    Report
        The ODF or built-in PDF report, followed by a requested veraPDF report for PDFs.

    """
    validate_timeout(timeout)
    source = Path(source)
    if on_progress is not None:
        on_progress("Audit document", "running")
    if not is_pdf(source):
        yield audit_odf(source, schema=schema)
        return
    yield audit_pdfua(source)
    if verapdf or verapdf_path:
        if on_progress is not None:
            on_progress("Validate PDF with veraPDF", "running")
        report, _result = check_pdfua(
            source, subject=str(source), executable=verapdf_path, timeout=timeout
        )
        yield report
