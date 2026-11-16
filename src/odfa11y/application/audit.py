# SPDX-License-Identifier: MPL-2.0
"""Capture and inspect each input with tools resolved by the use case."""

from collections.abc import Iterator
from pathlib import Path

from odfa11y.application.compare import is_pdf
from odfa11y.application.native import NativeTools
from odfa11y.audit.engine import audit_document as audit_odf_document
from odfa11y.audit.validation import check_pdfua
from odfa11y.capture import capture_source
from odfa11y.errors import DocumentRefusal, PackageError
from odfa11y.native.tools import ResolvedTools
from odfa11y.odf import OdfDocument, Use
from odfa11y.pdf import audit_pdfua
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules


def audit_document(
    source: str | Path,
    *,
    schema: bool = False,
    tools: ResolvedTools,
    native_tools: NativeTools,
    on_progress: ProgressObserver | None = None,
) -> Iterator[Report]:
    """Retain completed PDF inspection if a requested validator execution later fails."""
    source = Path(source)
    with step(on_progress, Step.AUDIT_DOCUMENT), capture_source(source) as captured:
        if is_pdf(captured.path):
            report = audit_pdfua(captured.path)
            report.subject = str(source)
            report.sources = (source,)
            yield report
            if tools.verapdf is not None:
                with step(on_progress, Step.VALIDATE_PDF):
                    report, _ = check_pdfua(
                        captured.path,
                        subject=str(source),
                        tool=tools.verapdf,
                        timeout=tools.timeout,
                        validator=native_tools.validate,
                    )
                    report.sources = (source,)
                    yield report
            return
        try:
            document = OdfDocument.open(captured.path)
        except PackageError as error:
            with captured.path.open("rb") as stream:
                prefix = stream.read(4)
            if not prefix.startswith((b"PK", b"<", b"\xef\xbb\xbf")):
                message = "Input is not an OpenDocument or PDF file"
                raise DocumentRefusal(message) from None
            # Corrupt recognized containers keep their diagnostic package audit.
            report = Report(kind=ReportKind.ODF, subject=str(source), _sources=(source,))
            report.raise_(rules.PKG001, str(error))
            yield report
            return
        try:
            document.require(Use.AUDIT)
        except PackageError:
            yield audit_odf_document(document, subject=str(source), source=source, schema=schema)
            return
        if document.kind is None:
            message = "Input is not an OpenDocument or PDF file"
            raise DocumentRefusal(message)
        yield audit_odf_document(document, subject=str(source), source=source, schema=schema)
