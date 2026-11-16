# SPDX-License-Identifier: MPL-2.0
"""Fixed stage order and artifact dependencies, independent of acceptance gates."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from odfa11y.audit.engine import audit_document
from odfa11y.audit.export import native_export_settings
from odfa11y.audit.validation import validate_pdfua
from odfa11y.errors import DocumentRefusal, IoFailure, OdfA11yError
from odfa11y.families.spec import PdfExport
from odfa11y.pdf.audit import inspect_pdf
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.pdf.validation import add_verapdf_findings
from odfa11y.progress import Stage, Step, StepState, step
from odfa11y.remediate import Candidate, execute_decisions
from odfa11y.remediate.execute import require_remediable
from odfa11y.report import Report, ReportKind
from odfa11y.run.record import StageResult
from odfa11y.run.state import PdfArtifact, RunState
from odfa11y.status import (
    Crashed,
    ExitStatus,
    NotApplicable,
    Passed,
    Profile,
    Refused,
    Skipped,
    SkipReason,
    StageOutcome,
    gate_outcome,
)


class Artifact(StrEnum):
    CANDIDATE = "candidate"
    SOURCE_PDF = "source_pdf"
    CANDIDATE_PDF = "candidate_pdf"

    @property
    def meaning(self) -> str:
        return {
            self.CANDIDATE: "The guarded in-memory remediation candidate.",
            self.SOURCE_PDF: "The captured source's native PDF export.",
            self.CANDIDATE_PDF: "The guarded candidate's native PDF export.",
        }[self]


@dataclass(frozen=True, slots=True)
class StageSpec:
    name: Stage
    minimum: Profile
    inputs: tuple[Artifact, ...]
    run: Callable[[RunState], tuple[RunState, StageResult]]


def _audit_source(state: RunState) -> tuple[RunState, StageResult]:
    report = audit_document(state.document, subject=state.source.identity.name, schema=True)
    return replace(state, source_report=report), StageResult(Stage.AUDIT_SOURCE, Passed(report))


def _remediate(state: RunState) -> tuple[RunState, StageResult]:
    require_remediable(state.document, state.source.identity.path)
    candidate = execute_decisions(
        state.document, state.source.identity.path, state.decisions, plan=state.plan
    )
    if not isinstance(candidate, Candidate):
        message = "; ".join(item.message for item in candidate.result.violations)
        return state, StageResult(
            Stage.REMEDIATE, Refused(DocumentRefusal(message)), candidate.result
        )
    path = state.work / ("remediated" + state.source.path.suffix)
    candidate.materialize(path)
    return replace(state, candidate=candidate, candidate_path=path), StageResult(
        Stage.REMEDIATE, Passed(), candidate.result
    )


def _audit_candidate(state: RunState) -> tuple[RunState, StageResult]:
    candidate = _input(state.candidate)
    # Guarded execution already audits this exact in-memory candidate.
    report = candidate.result.candidate
    report = _input(report)
    report.subject = "remediated" + state.source.path.suffix
    return replace(state, candidate_report=report), StageResult(
        Stage.AUDIT_REMEDIATED, gate_outcome(report, strict=state.profile.strict)
    )


def _export(state: RunState, *, candidate: bool) -> tuple[RunState, StageResult]:
    name = Stage.EXPORT_REMEDIATED if candidate else Stage.EXPORT_SOURCE
    if not isinstance(state.family.export, PdfExport):
        reason = state.family.export.reason
        outcome: StageOutcome[Report] = (
            Refused(DocumentRefusal(reason))
            if state.profile is Profile.PRODUCTION
            else NotApplicable(reason)
        )
        return state, StageResult(name, outcome)
    document = state.candidate.document if candidate and state.candidate else state.document
    office = state.tools.libreoffice
    office = _input(office)
    path = state.candidate_path if candidate else state.source.path
    path = _input(path)
    output = state.work / ("remediated.pdf" if candidate else "source.pdf")
    settings = native_export_settings(
        document, office, state.tools.timeout, state.work / "profile", captured_identity=True
    )
    state.operations.export(path, output, settings)
    updated = (
        replace(state, candidate_pdf=PdfArtifact(output))
        if candidate
        else replace(state, source_pdf=PdfArtifact(output))
    )
    return updated, StageResult(name, Passed())


def _export_source(state: RunState) -> tuple[RunState, StageResult]:
    return _export(state, candidate=False)


def _export_candidate(state: RunState) -> tuple[RunState, StageResult]:
    return _export(state, candidate=True)


def _audit_pdf(state: RunState) -> tuple[RunState, StageResult]:
    candidate_pdf = _input(state.candidate_pdf)
    inspection = inspect_pdf(candidate_pdf.path)
    inspection.report.subject = "remediated.pdf"
    source_fonts = inspect_pdf(state.source_pdf.path).fonts if state.source_pdf else None
    return replace(
        state,
        pdf_report=inspection.report,
        source_fonts=source_fonts,
        candidate_fonts=inspection.fonts,
    ), StageResult(Stage.AUDIT_PDF, gate_outcome(inspection.report, strict=state.profile.strict))


def _validate(state: RunState) -> tuple[RunState, StageResult]:
    candidate_pdf = _input(state.candidate_pdf)
    validator = _input(state.tools.verapdf)
    result = validate_pdfua(
        candidate_pdf.path,
        tool=validator,
        validator=state.operations.validate,
        timeout=state.tools.timeout,
    )
    report = Report(kind=ReportKind.PDF_VALIDATION, subject="remediated.pdf")
    add_verapdf_findings(report, result)
    return replace(state, validation=result), StageResult(
        Stage.VALIDATE_PDF, gate_outcome(report, strict=state.profile.strict)
    )


def _fidelity(state: RunState) -> tuple[RunState, StageResult]:
    source_pdf = _input(state.source_pdf)
    candidate_pdf = _input(state.candidate_pdf)
    result = compare_pdfs(
        source_pdf.path,
        candidate_pdf.path,
        state.plan.fidelity,
        diff_dir=state.work / "diff",
        render=state.operations.render,
    )
    report = result.report
    report.subject = "remediated.pdf vs source.pdf"
    return replace(state, fidelity=result), StageResult(
        Stage.FIDELITY, gate_outcome(report, strict=state.profile.strict)
    )


STAGES = (
    StageSpec(Stage.AUDIT_SOURCE, Profile.SOURCE, (), _audit_source),
    StageSpec(Stage.EXPORT_SOURCE, Profile.PDF, (), _export_source),
    StageSpec(Stage.REMEDIATE, Profile.SOURCE, (), _remediate),
    StageSpec(Stage.AUDIT_REMEDIATED, Profile.SOURCE, (Artifact.CANDIDATE,), _audit_candidate),
    StageSpec(Stage.EXPORT_REMEDIATED, Profile.PDF, (Artifact.CANDIDATE,), _export_candidate),
    StageSpec(Stage.AUDIT_PDF, Profile.PDF, (Artifact.CANDIDATE_PDF,), _audit_pdf),
    StageSpec(Stage.VALIDATE_PDF, Profile.PRODUCTION, (Artifact.CANDIDATE_PDF,), _validate),
    StageSpec(
        Stage.FIDELITY, Profile.PDF, (Artifact.SOURCE_PDF, Artifact.CANDIDATE_PDF), _fidelity
    ),
)


def run_stage(spec: StageSpec, state: RunState) -> tuple[RunState, StageResult]:
    with step(state.observer, Step(spec.name)) as progress:
        if state.profile < spec.minimum:
            progress.state = StepState.SKIPPED
            return state, StageResult(spec.name, Skipped(SkipReason.PROFILE))
        for artifact in spec.inputs:
            if getattr(state, artifact.value) is None:
                producer = {
                    Artifact.CANDIDATE: Stage.REMEDIATE,
                    Artifact.SOURCE_PDF: Stage.EXPORT_SOURCE,
                    Artifact.CANDIDATE_PDF: Stage.EXPORT_REMEDIATED,
                }[artifact]
                progress.state = StepState.SKIPPED
                return state, StageResult(spec.name, Skipped(SkipReason.MISSING_INPUT, producer))
        try:
            updated, result = spec.run(state)
        except OSError as error:
            result = StageResult(spec.name, Crashed(IoFailure.from_oserror(error)))
            updated = state
        except OdfA11yError as error:
            result = StageResult(
                spec.name,
                Crashed(error)
                if error.exit_status is ExitStatus.EXECUTION_FAILURE
                else Refused(error),
            )
            updated = state
        if result.outcome.exit_status(state.profile.strict):
            progress.state = StepState.FAILED
        elif isinstance(result.outcome, NotApplicable):
            progress.state = StepState.SKIPPED
        return updated, result


def _input[T](value: T | None) -> T:
    if value is None:
        message = "Stage invoked without its declared input"
        raise ValueError(message)
    return value
