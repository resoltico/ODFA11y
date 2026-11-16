# SPDX-License-Identifier: MPL-2.0
"""Application use cases own input policy, continuation and effective result statuses."""

from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Literal
lazy from collections.abc import Callable, Sequence

from odfa11y.application.doctor import DoctorResult as DoctorResult
from odfa11y.application.doctor import doctor as doctor
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit import prepare_plan
from odfa11y.batch import run_batch as execute_batch
from odfa11y.contracts import JsonProperty, record_dict
from odfa11y.errors import Failure, IoFailure, OdfA11yError
from odfa11y.evidence import check_bundle
from odfa11y.native.process import termination_interrupt
from odfa11y.plans import Plan
from odfa11y.plans.fidelity import FidelityPolicy as FidelityPolicy
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan
from odfa11y.remediate import remediate as apply_plan
from odfa11y.report import exit_status, render_reports
from odfa11y.run.comparison import compare_documents
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.inspection import audit_document
from odfa11y.run.native import export_document
from odfa11y.run.profiles import DEFAULT_PROFILE
from odfa11y.status import ExitStatus, combine_statuses, failure_status
lazy from odfa11y.batch.record import BatchRecord
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.progress import ProgressObserver
lazy from odfa11y.remediate import RemediationResult
lazy from odfa11y.report import Report
lazy from odfa11y.run.profiles import Profile
lazy from odfa11y.run.record import RunRecord


def _interruptible[**P, R](operation: Callable[P, R]) -> Callable[P, R]:
    @wraps(operation)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
        with termination_interrupt():
            try:
                return operation(*args, **kwargs)
            except OSError as error:
                raise IoFailure.from_oserror(error) from error

    return invoke


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
    def source_name(self) -> str:
        """Return the source filename without its parent directories."""
        return self._source.name


@dataclass(frozen=True, slots=True)
class AuditRun:
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
            *(failure_status(item.error) for item in self.failures if item.error is not None),
        ])

    def render(
        self, output_format: str = "text", *, source_root: str | Path | None = None
    ) -> str | None:
        """Render completed checks with fail-closed SARIF semantics.

        Returns
        -------
        str | None
            Rendered checks, or no payload when every input failed before producing a report.

        """
        if output_format == "sarif":
            for item in self.failures:
                if item.error is not None:
                    raise item.error
        return (
            render_reports(
                self.reports,
                output_format=output_format,
                source_root=Path(source_root) if source_root is not None else None,
            )
            if self.reports
            else None
        )

    def as_dict(self) -> JsonObject:
        """Serialize per-input completion/failure evidence.

        Returns
        -------
        JsonObject
            The versioned multi-input record.

        """
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class PlanResult:
    """A source report and its bound disabled-answer template when planning is possible."""

    schema_version: Literal[1] = field(default=1, init=False)

    report: Report
    template: str | None

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether a reviewable plan was prepared."""
        return ExitStatus.PASSED if self.template is not None else exit_status([self.report])

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """The published PDF path and effective export status."""

    schema_version: Literal[1] = field(default=1, init=False)

    _output: Path

    @property
    def output(self) -> Path:
        """Return the published path for a subsequent application operation."""
        return self._output

    @JsonProperty
    def output_name(self) -> str:
        """Return the published filename without exposing its parent directories."""
        return self._output.name

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Return the completed export's effective status."""
        return ExitStatus.PASSED

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """A fidelity report under an explicit acceptance policy."""

    schema_version: Literal[1] = field(default=1, init=False)

    report: Report
    strict: bool = False

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Return the comparison's effective acceptance status."""
        return exit_status([self.report], strict=self.strict)

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Recorded-file integrity problems, independent of accessibility claims."""

    schema_version: Literal[1] = field(default=1, init=False)

    problems: tuple[str, ...]

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether every recorded integrity check passed."""
        return ExitStatus.ERRORS if self.problems else ExitStatus.PASSED

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


def _selected_plan(value: Plan | str | Path) -> Plan:
    return value if isinstance(value, Plan) else load_plan(value)


@_interruptible
def audit(
    sources: str | Path | Sequence[str | Path],
    *,
    tools: Tools | None = None,
    schema: bool = False,
    validate_pdf: bool = False,
    strict: bool = False,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> AuditRun:
    """Inspect independent inputs, retaining completed checks through later failures.

    Returns
    -------
    AuditRun
        Per-input outcomes with one combined acceptance status.

    """
    tools = tools or Tools()
    selected = (sources,) if isinstance(sources, str | Path) else tuple(sources)
    inputs = []
    for source in selected:
        reports = []
        error = None
        try:
            reports.extend(
                audit_document(
                    source,
                    schema=schema,
                    verapdf=validate_pdf,
                    verapdf_path=tools.verapdf,
                    timeout=tools.timeout,
                    on_progress=observer,
                    native_tools=native_tools,
                )
            )
        except (OdfA11yError, OSError) as exc:
            error = IoFailure.from_oserror(exc) if isinstance(exc, OSError) else exc
        inputs.append(AuditInput(Path(source), tuple(reports), error))
    return AuditRun(tuple(inputs), strict)


@_interruptible
def plan(
    source: str | Path, *, from_plan: Plan | str | Path | None = None, include_all: bool = False
) -> PlanResult:
    """Prepare source-bound human questions without changing the document.

    Returns
    -------
    PlanResult
        The source report and optional reviewed-answer template.

    """
    previous = _selected_plan(from_plan) if from_plan is not None else None
    report, template = prepare_plan(source, previous=previous, include_all=include_all)
    return PlanResult(report, template)


@_interruptible
def remediate(
    source: str | Path,
    destination: str | Path,
    plan: Plan | str | Path,
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Apply reviewed answers under source, preservation and publication guards.

    Returns
    -------
    RemediationResult
        Every operation outcome and the physical publication result.

    """
    return apply_plan(source, destination, plan, dry_run=dry_run)


@_interruptible
def export(
    source: str | Path,
    destination: str | Path,
    *,
    tools: Tools | None = None,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> ExportResult:
    """Publish a guarded native export with caller-selected tools.

    Returns
    -------
    ExportResult
        The published PDF and effective status.

    """
    return ExportResult(
        export_document(
            source, destination, tools or Tools(), on_progress=observer, native_tools=native_tools
        )
    )


@_interruptible
def compare(
    source: str | Path,
    candidate: str | Path,
    *,
    tools: Tools | None = None,
    plan: Plan | str | Path | None = None,
    diff_dir: str | Path | None = None,
    strict: bool = False,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> ComparisonResult:
    """Compare original ODF/PDF inputs under the selected fidelity policy.

    Returns
    -------
    ComparisonResult
        Fidelity findings and effective strict acceptance.

    """
    policy = _selected_plan(plan).fidelity if plan is not None else Pagination.SAME()
    return ComparisonResult(
        compare_documents(
            source,
            candidate,
            policy,
            diff_dir,
            tools or Tools(),
            on_progress=observer,
            native_tools=native_tools,
        ),
        strict,
    )


@_interruptible
def run(
    source: str | Path,
    plan: Plan | str | Path,
    output_dir: str | Path,
    *,
    tools: Tools | None = None,
    profile: Profile = DEFAULT_PROFILE,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> RunRecord:
    """Execute the selected assurance profile and publish reviewable evidence.

    Returns
    -------
    RunRecord
        Typed stages, effective status and retained evidence.

    """
    return execute(
        source,
        _selected_plan(plan),
        output_dir,
        RunSettings(tools or Tools(), profile, observer),
        native_tools=native_tools,
    )


@_interruptible
def run_batch(
    manifest: str | Path,
    output_dir: str | Path,
    *,
    tools: Tools | None = None,
    profile: Profile = DEFAULT_PROFILE,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> BatchRecord:
    """Execute independent manifest entries with one batch-lifetime native probe cache.

    Returns
    -------
    BatchRecord
        Per-item outcomes and the combined effective status.

    """
    return execute_batch(
        manifest,
        output_dir,
        RunSettings(tools or Tools(), profile),
        on_progress=observer,
        native_tools=native_tools,
    )


@_interruptible
def verify_evidence(directory: str | Path) -> VerificationResult:
    """Check recorded file integrity without claiming document accessibility.

    Returns
    -------
    VerificationResult
        Every integrity problem and effective status.

    """
    return VerificationResult(tuple(check_bundle(directory)))
