# SPDX-License-Identifier: MPL-2.0
"""Run the whole remediation workflow and publish its evidence."""

from __future__ import annotations

import tempfile
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odf, template_blockers
from odfa11y.errors import PackageError
from odfa11y.evidence import require_free_directory, sha256_file
from odfa11y.families import GENERIC, adapter_for
from odfa11y.fidelity import compare_pdfs
from odfa11y.odf import OdfDocument, declared_version
from odfa11y.outcomes import (
    PIPELINE_STAGES,
    ProgressEvent,
    StageName,
    StageStatus,
    StepName,
    StepState,
)
from odfa11y.pdf import (
    ExportSettings,
    audit_pdfua,
    check_pdfua,
    export_pdfua,
    find_soffice,
    identify_soffice,
    link_descriptions_supported,
    list_fonts,
)
from odfa11y.records import DocumentIdentity
from odfa11y.remediation import remediate
from odfa11y.report import exit_status

from .native import native_export_settings
from .publication import publish_evidence
from .record import PipelineOptions, RunRecord, StageResult
from .source import capture_source
from .stages import run_stage

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.adapter import FamilyAdapter, Operation
    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.report import Report


@dataclass(slots=True)
class _Run:
    source: Path
    work: Path
    operations: Sequence[Operation]
    policy: FidelityPolicy
    record: RunRecord
    options: PipelineOptions
    lifetime: ExitStack
    captured: Path | None = None
    adapter: FamilyAdapter = GENERIC
    executable: str | None = None

    # Stage methods raise OdfA11yError or OSError on execution failure; run_pipeline turns
    # either into a failed stage, so no failure can prevent the evidence from being written.

    @property
    def remediated(self) -> Path:
        return self.work / f"remediated{self.source.suffix}"

    def identify_source(self) -> StageResult:
        self.captured = self.lifetime.enter_context(capture_source(self.source))
        self.record.document.sha256 = sha256_file(self.captured)
        try:
            document = OdfDocument.open(self.captured)
        except PackageError, OSError:
            return StageResult(
                StageName.IDENTIFY_SOURCE, StageStatus.PASSED, gate=False
            )  # audit-source explains
        if document.protection.inspection_blocked:
            return StageResult(
                StageName.IDENTIFY_SOURCE, StageStatus.PASSED, gate=False
            )  # audit-source explains
        detection = document.detection
        self.adapter = adapter_for(detection.kind)
        self.record.document = DocumentIdentity(
            name=self.record.document.name,
            sha256=self.record.document.sha256,
            kind=detection.kind.name if detection.kind else None,
            media_type=detection.media_type,
            layout=document.layout,
            family=detection.kind.family.value if detection.kind else None,
            adapter=self.adapter.name,
            odf_version=declared_version(document),
        )
        self.record.human_review = self.adapter.review_items
        return StageResult(StageName.IDENTIFY_SOURCE, StageStatus.PASSED, gate=False)

    def audit_source(self) -> StageResult:
        report = audit_odf(self.captured or self.source, schema=True)
        report.subject = self.source.name
        blocked = template_blockers(report) is not None
        return StageResult(
            StageName.AUDIT_SOURCE,
            StageStatus.FAILED if blocked else StageStatus.PASSED,
            "source is not a readable ODF document" if blocked else None,
            report=report,
            gate=blocked,
        )

    def remediate(self) -> StageResult:
        result = remediate(self.captured or self.source, self.remediated, self.operations)
        return StageResult(
            StageName.REMEDIATE,
            StageStatus.PASSED,
            remediation=replace(result, source=self.source),
            gate=False,
        )

    def audit_remediated(self) -> StageResult:
        report = audit_odf(self.remediated)
        report.subject = self.remediated.name
        return self._gate(StageName.AUDIT_REMEDIATED, report)

    def export_source(self) -> StageResult:
        return self._export(StageName.EXPORT_SOURCE, self.captured or self.source, "source.pdf")

    def export_remediated(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(StageName.EXPORT_REMEDIATED)
        native_export_settings(
            OdfDocument.open(self.remediated),
            self.options.soffice,
            self.options.timeout,
            captured_identity=True,
        )
        with capture_source(
            self.remediated, directory=(self.captured or self.source).parent
        ) as staged:
            return self._export(StageName.EXPORT_REMEDIATED, staged, "remediated.pdf")

    def audit_pdf(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(StageName.AUDIT_PDF)
        self.record.fonts = {
            "source": list_fonts(self.work / "source.pdf"),
            "remediated": list_fonts(self.work / "remediated.pdf"),
        }
        report = audit_pdfua(self.work / "remediated.pdf")
        report.subject = "remediated.pdf"
        return self._gate(StageName.AUDIT_PDF, report)

    def validate_pdfua(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(StageName.VALIDATE_PDF)
        report, result = check_pdfua(
            self.work / "remediated.pdf",
            subject="remediated.pdf",
            executable=self.options.verapdf_path,
            timeout=self.options.timeout,
        )
        if result is None:
            required = self.record.profile.verapdf_required
            return StageResult(
                StageName.VALIDATE_PDF,
                StageStatus.FAILED if required else StageStatus.SKIPPED,
                "veraPDF unavailable",
                report=report,
                error=required,
            )
        (self.work / "verapdf.xml").write_text(result.raw_xml, encoding="utf-8")
        self.record.toolchain.verapdf = result.identity
        return self._gate(StageName.VALIDATE_PDF, report)

    def fidelity(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf(StageName.FIDELITY)
        report = compare_pdfs(
            self.work / "source.pdf",
            self.work / "remediated.pdf",
            self.policy,
            diff_dir=self.work / StageName.FIDELITY,
        )
        report.subject = "remediated.pdf vs source.pdf"
        return self._gate(StageName.FIDELITY, report)

    @property
    def _exportable(self) -> bool:
        return self.adapter.pdf_filter is not None

    def _no_pdf(self, name: StageName) -> StageResult:
        kind = self.record.document.kind or "this kind of"
        reason = f"no PDF export is defined for {kind} documents"
        if self.record.profile.verapdf_required:
            return StageResult(
                name,
                StageStatus.FAILED,
                f"{reason}; the profile requires PDF validation",
                error=True,
            )
        return StageResult(name, StageStatus.NOT_APPLICABLE, reason, gate=False)

    def _gate(self, name: StageName, report: Report) -> StageResult:
        failed = exit_status([report], strict=self.record.strict) != 0
        return StageResult(
            name, StageStatus.FAILED if failed else StageStatus.PASSED, report=report
        )

    def _export(self, name: StageName, document: Path, pdf_name: str) -> StageResult:
        if self.adapter.pdf_filter is None:
            return self._no_pdf(name)
        settings = native_export_settings(
            OdfDocument.open(document),
            self.executable or self.options.soffice,
            self.options.timeout,
            self.work / "profile",
            captured_identity=True,
        )
        if self.executable is None:
            self.executable = find_soffice(self.options.soffice)
            self.record.toolchain.libreoffice = identify_soffice(self.executable)
            if self.adapter.link_probe is not None:
                with tempfile.TemporaryDirectory(prefix="odfa11y-link-probe-") as scratch:
                    probe = self.adapter.link_probe(Path(scratch))
                    supported = link_descriptions_supported(
                        probe,
                        ExportSettings(
                            self.adapter.pdf_filter,
                            self.executable,
                            self.options.timeout,
                            self.work / "profile",
                        ),
                    )
                self.record.toolchain.capabilities["pdfua_link_descriptions"] = (
                    "supported" if supported else "unsupported"
                )
        export_pdfua(
            document,
            self.work / pdf_name,
            replace(settings, soffice=self.executable),
        )
        return StageResult(name, StageStatus.PASSED, gate=False)


def run_pipeline(
    source: str | Path,
    operations: Sequence[Operation],
    policy: FidelityPolicy,
    output_dir: str | Path,
    options: PipelineOptions | None = None,
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
    options = options or PipelineOptions()
    on_progress = options.on_progress
    profile = options.assurance
    source, target = Path(source), Path(output_dir)
    require_free_directory(target)
    record = RunRecord(
        document=DocumentIdentity(source.name),
        operations=tuple(operation.as_dict() for operation in operations),
        policy=policy,
        profile=profile,
        human_review=GENERIC.review_items,
    )
    with ExitStack() as lifetime, tempfile.TemporaryDirectory(prefix="odfa11y-run-") as scratch:
        work = Path(scratch)
        run = _Run(source, work, operations, policy, record, options, lifetime)
        steps: dict[StageName, Callable[[], StageResult]] = {
            StageName.IDENTIFY_SOURCE: run.identify_source,
            StageName.AUDIT_SOURCE: run.audit_source,
            StageName.REMEDIATE: run.remediate,
            StageName.AUDIT_REMEDIATED: run.audit_remediated,
            StageName.EXPORT_SOURCE: run.export_source,
            StageName.EXPORT_REMEDIATED: run.export_remediated,
            StageName.AUDIT_PDF: run.audit_pdf,
            StageName.VALIDATE_PDF: run.validate_pdfua,
            StageName.FIDELITY: run.fidelity,
        }
        for name in PIPELINE_STAGES:
            stage = run_stage(name, steps[name], record, on_progress=on_progress)
            record.stages.append(stage)
            if on_progress is not None:
                on_progress(
                    ProgressEvent(
                        StepName(name),
                        StepState.SKIPPED
                        if stage.status == StageStatus.NOT_APPLICABLE
                        else StepState(stage.status),
                    )
                )
        publish_evidence(source, target, work, record, on_progress)
    return record
