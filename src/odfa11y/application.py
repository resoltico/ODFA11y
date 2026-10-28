# SPDX-License-Identifier: MPL-2.0
"""Application use cases own input policy, continuation and effective result statuses."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from odfa11y.batch import run_batch as execute_batch
from odfa11y.errors import OdfA11yError
from odfa11y.evidence import check_bundle
from odfa11y.native.process import termination_interrupt
from odfa11y.outcomes import ExitStatus, combine_statuses, failure_status
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.comparison import compare_documents
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.diagnostics import inspect_tools
from odfa11y.pipeline.engine import execute
from odfa11y.pipeline.inspection import audit_document
from odfa11y.pipeline.native import export_document
from odfa11y.pipeline.profiles import DEFAULT_PROFILE
from odfa11y.plans import Plan, load_plan
from odfa11y.remediation import remediate as apply_plan
from odfa11y.report import exit_status, render_reports
from odfa11y.serialization import JsonProperty, record_dict
from odfa11y.source_audit import prepare_plan
from odfa11y.tools import Tools

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.batch.record import BatchRecord
    from odfa11y.outcomes import ProgressObserver
    from odfa11y.pipeline.profiles import Profile
    from odfa11y.pipeline.record import RunRecord
    from odfa11y.records import DoctorRecord
    from odfa11y.remediation import RemediationResult
    from odfa11y.report import Report
    from odfa11y.serialization import JsonObject


def _interruptible[**P, R](operation: Callable[P, R]) -> Callable[P, R]:
    @wraps(operation)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
        with termination_interrupt():
            return operation(*args, **kwargs)

    return invoke


@dataclass(frozen=True, slots=True)
class AuditFailure:
    """An input's effective failure status and actionable message."""

    exit_status: ExitStatus
    message: str


@dataclass(frozen=True, slots=True)
class AuditInput:
    """Completed checks survive a later failure for the same physical input."""

    source: Path = field(metadata={"basename": True})
    reports: tuple[Report, ...]
    error: OdfA11yError | OSError | ValueError | None = field(
        default=None, metadata={"serialize": False}
    )

    @JsonProperty
    def failure(self) -> AuditFailure | None:
        """The failure derived from the original error, if inspection was incomplete."""
        return AuditFailure(failure_status(self.error), str(self.error)) if self.error else None


@dataclass(frozen=True, slots=True)
class AuditRun:
    """All independent input outcomes and the effective strict-acceptance status."""

    inputs: tuple[AuditInput, ...]
    strict: bool = False
    format: Literal[1] = field(default=1, init=False)

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

    report: Report
    template: str | None

    @property
    def exit_status(self) -> ExitStatus:
        """Whether a reviewable plan was prepared."""
        return ExitStatus.PASSED if self.template is not None else exit_status([self.report])


@dataclass(frozen=True, slots=True)
class ExportResult:
    """The published PDF path and effective export status."""

    output: Path
    exit_status: ExitStatus = field(default=ExitStatus.PASSED, init=False)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """A fidelity report under an explicit acceptance policy."""

    report: Report
    strict: bool = False

    @property
    def exit_status(self) -> ExitStatus:
        """The comparison's effective acceptance status."""
        return exit_status([self.report], strict=self.strict)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Recorded-file integrity problems, independent of accessibility claims."""

    problems: tuple[str, ...]

    @property
    def exit_status(self) -> ExitStatus:
        """Whether every recorded integrity check passed."""
        return ExitStatus.ERRORS if self.problems else ExitStatus.PASSED


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
                )
            )
        except (OdfA11yError, OSError, ValueError) as exc:
            error = exc
        inputs.append(AuditInput(Path(source), tuple(reports), error))
    return AuditRun(tuple(inputs), strict)


@_interruptible
def plan(source: str | Path) -> PlanResult:
    """Prepare source-bound human questions without changing the document.

    Returns
    -------
    PlanResult
        The source report and optional reviewed-answer template.

    """
    report, template = prepare_plan(source)
    return PlanResult(report, template)


@_interruptible
def remediate(
    source: str | Path,
    destination: str | Path,
    plan: Plan | str | Path,
    *,
    dry_run: bool = False,
    rebind: bool = False,
) -> RemediationResult:
    """Apply reviewed answers under source, preservation and publication guards.

    Returns
    -------
    RemediationResult
        Every operation outcome and the physical publication result.

    """
    return apply_plan(source, destination, _selected_plan(plan), dry_run=dry_run, rebind=rebind)


@_interruptible
def export(
    source: str | Path,
    destination: str | Path,
    *,
    tools: Tools | None = None,
    observer: ProgressObserver | None = None,
) -> ExportResult:
    """Publish a guarded native export with caller-selected tools.

    Returns
    -------
    ExportResult
        The published PDF and effective status.

    """
    return ExportResult(
        export_document(source, destination, tools or Tools(), on_progress=observer)
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
) -> ComparisonResult:
    """Compare original ODF/PDF inputs under the selected fidelity policy.

    Returns
    -------
    ComparisonResult
        Fidelity findings and effective strict acceptance.

    """
    policy = _selected_plan(plan).fidelity if plan is not None else FidelityPolicy()
    return ComparisonResult(
        compare_documents(
            source, candidate, policy, diff_dir, tools or Tools(), on_progress=observer
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
    rebind: bool = False,
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
        rebind=rebind,
    )


@_interruptible
def run_batch(
    manifest: str | Path,
    output_dir: str | Path,
    *,
    tools: Tools | None = None,
    profile: Profile = DEFAULT_PROFILE,
    observer: ProgressObserver | None = None,
    rebind: bool = False,
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
        rebind=rebind,
    )


@_interruptible
def doctor(*, tools: Tools | None = None, observer: ProgressObserver | None = None) -> DoctorRecord:
    """Measure dependency identities and every declared native capability.

    Returns
    -------
    DoctorRecord
        All observations, any controlled error and the effective execution status.

    """
    record, error = inspect_tools(tools or Tools(), on_progress=observer)
    record.error = error
    return record


@_interruptible
def verify_evidence(directory: str | Path) -> VerificationResult:
    """Check recorded file integrity without claiming document accessibility.

    Returns
    -------
    VerificationResult
        Every integrity problem and effective status.

    """
    return VerificationResult(tuple(check_bundle(directory)))
