# SPDX-License-Identifier: MPL-2.0
"""Run the whole remediation workflow and publish its evidence."""

import tempfile
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path
lazy from collections.abc import Callable

from odfa11y.application.native import NativeTools
from odfa11y.audit import audit_odf, plan_blockers
from odfa11y.audit.validation import check_pdfua
from odfa11y.capture import capture_source, source_digest
from odfa11y.errors import PackageError
from odfa11y.evidence import require_free_directory
from odfa11y.families import spec_for
from odfa11y.families.probes import ProbeCache
from odfa11y.families.spec import PdfExport
from odfa11y.odf import OdfDocument, Use, declared_version
from odfa11y.pdf import audit_pdfua, list_fonts
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.progress import PIPELINE_STAGES, ProgressEvent, Stage, Step, StepState
from odfa11y.records import DocumentIdentity
from odfa11y.remediate import remediate
from odfa11y.report import exit_status
from odfa11y.run.context import RunSettings
from odfa11y.run.native import native_export_settings
from odfa11y.run.publication import publish_evidence
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.run.stages import run_stage
from odfa11y.status import StageStatus
lazy from odfa11y.families.spec import FamilySpec
lazy from odfa11y.plans import Plan
lazy from odfa11y.report import Report


@dataclass(slots=True)
class _Run:
    source: Path
    work: Path
    plan: Plan
    record: RunRecord
    options: RunSettings
    lifetime: ExitStack
    probe_cache: ProbeCache = field(default_factory=ProbeCache)
    captured: Path | None = None
    adapter: FamilySpec | None = None
    executable: str | None = None
    native_tools: NativeTools = field(default_factory=NativeTools)

    # Stage methods raise OdfA11yError or OSError on execution failure; execute turns
    # either into a failed stage, so no failure can prevent the evidence from being written.

    @property
    def remediated(self) -> Path:
        return self.work / f"remediated{self.source.suffix}"

    def identify_source(self) -> StageResult:
        self.captured = self.lifetime.enter_context(capture_source(self.source))
        self.record.document.sha256 = source_digest(self.captured)
        try:
            document = OdfDocument.open(self.captured)
        except PackageError, OSError:
            return StageResult(
                Stage.IDENTIFY_SOURCE, StageStatus.PASSED, _gate=False
            )  # audit-source explains
        try:
            document.require(Use.AUDIT)
        except PackageError:
            return StageResult(
                Stage.IDENTIFY_SOURCE, StageStatus.PASSED, _gate=False
            )  # audit-source explains
        detection = document.detection
        self.adapter = spec_for(detection.kind)
        self.record.document = DocumentIdentity(
            name=self.record.document.name,
            sha256=self.record.document.sha256,
            kind=detection.kind.name if detection.kind else None,
            media_type=detection.media_type,
            layout=document.layout,
            family=detection.kind.family.value if detection.kind else None,
            adapter=self.adapter.family.value if self.adapter else None,
            odf_version=declared_version(document),
        )
        self.record.human_review = self.adapter.review_items if self.adapter else ()
        return StageResult(Stage.IDENTIFY_SOURCE, StageStatus.PASSED, _gate=False)

    def audit_source(self) -> StageResult:
        report = audit_odf(self.captured or self.source, schema=True)
        report.subject = self.source.name
        blocked = plan_blockers(report) is not None
        return StageResult(
            Stage.AUDIT_SOURCE,
            StageStatus.FAILED if blocked else StageStatus.PASSED,
            "source is not a readable ODF document" if blocked else None,
            report=report,
            _gate=blocked,
        )

    def remediate(self) -> StageResult:
        result = remediate(self.captured or self.source, self.remediated, self.plan)
        if result.candidate is not None:
            result.candidate.subject = self.remediated.name
        return StageResult(
            Stage.REMEDIATE,
            StageStatus.PASSED if result.published else StageStatus.FAILED,
            reason="; ".join(item.message for item in result.violations) or None,
            remediation=replace(result, _source=self.source),
            _gate=not result.published,
        )

    def audit_remediated(self) -> StageResult:
        report = audit_odf(self.remediated)
        report.subject = self.remediated.name
        return self._gate(Stage.AUDIT_REMEDIATED, report)

    def export_source(self) -> StageResult:
        return self._export(Stage.EXPORT_SOURCE, self.captured or self.source, "source.pdf")

    def export_remediated(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(Stage.EXPORT_REMEDIATED)
        native_export_settings(
            OdfDocument.open(self.remediated),
            self.options.tools.soffice,
            self.options.tools.timeout,
            captured_identity=True,
        )
        with capture_source(
            self.remediated, directory=(self.captured or self.source).parent
        ) as staged:
            return self._export(Stage.EXPORT_REMEDIATED, staged, "remediated.pdf")

    def audit_pdf(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(Stage.AUDIT_PDF)
        self.record.fonts = {
            "source": list_fonts(self.work / "source.pdf"),
            "remediated": list_fonts(self.work / "remediated.pdf"),
        }
        report = audit_pdfua(self.work / "remediated.pdf")
        report.subject = "remediated.pdf"
        return self._gate(Stage.AUDIT_PDF, report)

    def validate_pdfua(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(Stage.VALIDATE_PDF)
        report, result = check_pdfua(
            self.work / "remediated.pdf",
            subject="remediated.pdf",
            executable=self.options.tools.verapdf,
            timeout=self.options.tools.timeout,
            validator=self.native_tools.validate,
            locate=self.native_tools.validator,
        )
        (self.work / "verapdf.xml").write_text(result.raw_xml, encoding="utf-8")
        self.record.toolchain.verapdf = result.identity
        return self._gate(Stage.VALIDATE_PDF, report)

    def fidelity(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(Stage.FIDELITY)
        report = compare_pdfs(
            self.work / "source.pdf",
            self.work / "remediated.pdf",
            self.plan.fidelity,
            diff_dir=self.work / Stage.FIDELITY,
            render=self.native_tools.render,
        )
        report.subject = "remediated.pdf vs source.pdf"
        return self._gate(Stage.FIDELITY, report)

    @property
    def _exportable(self) -> bool:
        return self.adapter is not None and isinstance(self.adapter.export, PdfExport)

    def _no_pdf(self, name: Stage) -> StageResult:
        kind = self.record.document.kind or "this kind of"
        reason = f"no PDF export is defined for {kind} documents"
        if self.record.profile.verapdf_required:
            return StageResult(
                name,
                StageStatus.FAILED,
                f"{reason}; the profile requires PDF validation",
                _error=True,
            )
        return StageResult(name, StageStatus.NOT_APPLICABLE, reason, _gate=False)

    def _gate(self, name: Stage, report: Report) -> StageResult:
        failed = exit_status([report], strict=self.record.strict) != 0
        return StageResult(
            name, StageStatus.FAILED if failed else StageStatus.PASSED, report=report
        )

    def _export(self, name: Stage, document: Path, pdf_name: str) -> StageResult:
        if self.adapter is None or not self._exportable:
            return self._no_pdf(name)
        settings = native_export_settings(
            OdfDocument.open(document),
            self.executable or self.options.tools.soffice,
            self.options.tools.timeout,
            self.work / "profile",
            captured_identity=True,
        )
        if self.executable is None:
            self.executable = self.native_tools.locate(self.options.tools.soffice)
            self.record.toolchain.libreoffice = self.native_tools.identify(self.executable)
            for probe in self.adapter.probes:
                if not probe.relevant(self.adapter.family, self.plan.decisions):
                    continue
                execution = self.probe_cache.run(
                    probe,
                    self.record.toolchain.libreoffice,
                    replace(settings, soffice=self.executable),
                    verapdf_path=self.options.tools.verapdf,
                    observer=self.options.on_progress,
                    export=self.native_tools.export,
                    validate=self.native_tools.validate,
                )
                self.record.toolchain.capabilities += (execution.result,)
                if execution.error is not None:
                    raise execution.error
        self.native_tools.export(
            document,
            self.work / pdf_name,
            replace(settings, soffice=self.executable),
        )
        return StageResult(name, StageStatus.PASSED, _gate=False)


def execute(
    source: str | Path,
    plan: Plan,
    output_dir: str | Path,
    options: RunSettings | None = None,
    *,
    probe_cache: ProbeCache | None = None,
    native_tools: NativeTools | None = None,
) -> RunRecord:
    """Identify, audit, remediate, export, validate and compare, then publish evidence.

    Stages run in a fixed order, only those the assurance profile and the document kind call
    for, and stop at the first failed gate; later stages are recorded as skipped. Once the
    output directory is acceptable, the bundle is published whether the run passed or failed,
    even when the source cannot be read. Progress observers receive fixed stage/status
    fields and must not raise; they do not alter the evidence record.

    Returns
    -------
    RunRecord
        The stage results; ``exit_status`` gives the command exit status.

    """
    options = options or RunSettings()
    on_progress = options.on_progress
    profile = options.profile
    source, target = Path(source), Path(output_dir)
    require_free_directory(target)
    record = RunRecord(
        document=DocumentIdentity(source.name),
        fidelity_policy=plan.fidelity,
        plan=plan.header,
        decisions=plan.decisions,
        profile=profile,
        human_review=(),
    )
    with ExitStack() as lifetime, tempfile.TemporaryDirectory(prefix="odfa11y-run-") as scratch:
        work = Path(scratch)
        run = _Run(
            source,
            work,
            plan,
            record,
            options,
            lifetime,
            probe_cache=probe_cache or ProbeCache(),
            native_tools=native_tools or NativeTools(),
        )
        steps: dict[Stage, Callable[[], StageResult]] = {
            Stage.IDENTIFY_SOURCE: run.identify_source,
            Stage.AUDIT_SOURCE: run.audit_source,
            Stage.REMEDIATE: run.remediate,
            Stage.AUDIT_REMEDIATED: run.audit_remediated,
            Stage.EXPORT_SOURCE: run.export_source,
            Stage.EXPORT_REMEDIATED: run.export_remediated,
            Stage.AUDIT_PDF: run.audit_pdf,
            Stage.VALIDATE_PDF: run.validate_pdfua,
            Stage.FIDELITY: run.fidelity,
        }
        for name in PIPELINE_STAGES:
            stage = run_stage(name, steps[name], record, on_progress=on_progress)
            record.stages.append(stage)
            if on_progress is not None:
                on_progress(
                    ProgressEvent(
                        Step(name),
                        StepState.SKIPPED
                        if stage.status == StageStatus.NOT_APPLICABLE
                        else StepState(stage.status),
                    )
                )
        publish_evidence(source, target, work, record, on_progress)
    return record
