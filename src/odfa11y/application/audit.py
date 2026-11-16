# SPDX-License-Identifier: AGPL-3.0-only
"""Capture and inspect each input with tools resolved by the use case."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from odfa11y.application.compare import is_pdf
from odfa11y.application.io_errors import translate_io
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit import plan_blockers
from odfa11y.audit.engine import audit_document as audit_odf_document
from odfa11y.audit.validation import check_pdfua
from odfa11y.capture import capture_source
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.errors import DocumentRefusal, Failure, IoFailure, OdfA11yError, PackageError
from odfa11y.native.tools import ResolvedTools
from odfa11y.odf import OdfDocument, Use
from odfa11y.odf.detect import is_odf_container
from odfa11y.pdf import audit_pdfua
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.report import Report, ReportKind, SarifOptions, exit_status
from odfa11y.rules import registry as rules
from odfa11y.status import ExitStatus, combine_statuses


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
            recognized = document.kind is not None or is_odf_container(document)
        except PackageError:
            yield audit_odf_document(document, subject=str(source), source=source, schema=schema)
            return
        if not recognized:
            message = "Input is not an OpenDocument or PDF file"
            raise DocumentRefusal(message)
        yield audit_odf_document(document, subject=str(source), source=source, schema=schema)


@dataclass(frozen=True, slots=True)
class AuditInput:
    """Completed checks survive a later failure for the same physical input."""

    _source: Path
    reports: tuple[Report, ...]
    _error: OdfA11yError | None = field(default=None)

    @JsonProperty
    def failure(self) -> Failure | None:
        """Return the failure derived from the original error, if inspection was incomplete."""
        return self._error.as_record() if self._error is not None else None

    @property
    def source(self) -> Path:
        """Return the inspected input path."""
        return self._source

    @property
    def error(self) -> OdfA11yError | None:
        """Return an incomplete inspection failure."""
        return self._error

    @JsonProperty
    def plannable(self) -> bool:
        """Whether source inspection established enough structure to prepare questions."""
        return self.error is None and any(
            report.kind is ReportKind.ODF and plan_blockers(report) is None
            for report in self.reports
        )

    @JsonProperty
    def source_name(self) -> str:
        """Return the source filename without its parent directories."""
        return self._source.name


@dataclass(frozen=True, slots=True)
class AuditResult:
    """All independent input outcomes and the effective strict-acceptance status."""

    inputs: tuple[AuditInput, ...]
    strict: bool = False
    schema_version: Literal[1] = field(default=1, init=False)

    @property
    def reports(self) -> tuple[Report, ...]:
        """Completed reports in input/check order."""
        return tuple(report for item in self.inputs for report in item.reports)

    @property
    def failures(self) -> tuple[AuditInput, ...]:
        """Inputs whose requested inspection did not complete."""
        return tuple(item for item in self.inputs if item.error is not None)

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Aggregate execution, usage and report gates by explicit precedence."""
        return combine_statuses([
            exit_status(self.reports, strict=self.strict),
            *(item.error.exit_status for item in self.failures if item.error is not None),
        ])

    def as_sarif(self, options: SarifOptions) -> JsonObject:
        """Refuse partial inspection before producing a privacy-preserving SARIF log."""
        for item in self.failures:
            if item.error is not None:
                raise item.error
        return options.log(self.reports)

    def as_dict(self) -> JsonObject:
        """Serialize per-input completion/failure evidence."""
        return record_dict(self)


@translate_io
def audit(
    sources: str | Path | Sequence[str | Path],
    *,
    tools: Tools | None = None,
    schema: bool = False,
    validate_pdf: bool = False,
    strict: bool = False,
    sarif: SarifOptions | None = None,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> AuditResult:
    """Inspect independent inputs, retaining completed checks through later failures."""
    selected = (sources,) if isinstance(sources, str | Path) else tuple(sources)
    if sarif is not None:
        sarif.preflight(selected)
    tools = tools or Tools()
    operations = native_tools or NativeTools()
    resolved = tools.resolve(verapdf=validate_pdf, native_tools=operations)
    inputs = []
    for source in selected:
        reports = []
        error = None
        try:
            reports.extend(
                audit_document(
                    source,
                    schema=schema,
                    tools=resolved,
                    on_progress=observer,
                    native_tools=operations,
                )
            )
        except (OdfA11yError, OSError) as exc:
            error = IoFailure.from_oserror(exc) if isinstance(exc, OSError) else exc
        inputs.append(AuditInput(Path(source), tuple(reports), error))
    return AuditResult(tuple(inputs), strict)
