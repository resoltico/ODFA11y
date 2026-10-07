# SPDX-License-Identifier: MPL-2.0
"""Run the whole remediation workflow and publish its evidence."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odt
from odfa11y.errors import OdfA11yError
from odfa11y.evidence import require_free_directory, sha256_file, write_bundle
from odfa11y.fidelity import compare_pdfs
from odfa11y.pdf import (
    audit_pdfua,
    check_pdfua,
    export_pdfua,
    find_soffice,
    identify_soffice,
)
from odfa11y.remediation import remediate
from odfa11y.report import exit_status, rules

from .record import STAGE_NAMES, PipelineOptions, RunRecord, StageResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.remediation import Operation
    from odfa11y.report import Report


@dataclass(slots=True)
class _Run:
    source: Path
    work: Path
    operations: Sequence[Operation]
    policy: FidelityPolicy
    record: RunRecord
    options: PipelineOptions
    executable: str | None = None

    # Stage methods raise OdfA11yError or OSError on execution failure; run_pipeline turns
    # either into a failed stage, so no failure can prevent the evidence from being written.

    def audit_source(self) -> StageResult:
        report = audit_odt(self.source, schema=True)
        report.subject = self.source.name
        unreadable = any(f.rule_id == rules.PKG000.id for f in report.findings)
        return StageResult(
            "audit-source",
            "failed" if unreadable else "passed",
            "source is not a readable ODT package" if unreadable else None,
            report=report,
            gate=unreadable,
        )

    def remediate(self) -> StageResult:
        result = remediate(self.source, self.work / "remediated.odt", self.operations)
        return StageResult("remediate", "passed", remediation=result, gate=False)

    def audit_remediated(self) -> StageResult:
        report = audit_odt(self.work / "remediated.odt")
        report.subject = "remediated.odt"
        return self._gate("audit-remediated", report)

    def export_source(self) -> StageResult:
        return self._export("export-source", self.source, "source.pdf")

    def export_remediated(self) -> StageResult:
        return self._export("export-remediated", self.work / "remediated.odt", "remediated.pdf")

    def audit_pdf(self) -> StageResult:
        report = audit_pdfua(self.work / "remediated.pdf")
        report.subject = "remediated.pdf"
        return self._gate("audit-pdf", report)

    def validate_pdfua(self) -> StageResult:
        if not self.options.wants_verapdf:
            return StageResult("verapdf", "skipped", "not requested", gate=False)
        report, result = check_pdfua(
            self.work / "remediated.pdf",
            subject="remediated.pdf",
            executable=self.options.verapdf_path,
        )
        if result is None:
            status = "failed" if self.record.strict else "skipped"
            return StageResult("verapdf", status, "veraPDF unavailable", report=report)
        (self.work / "verapdf.xml").write_text(result.raw_xml, encoding="utf-8")
        self.record.toolchain["veraPDF"] = result.identity.as_dict()
        return self._gate("verapdf", report)

    def fidelity(self) -> StageResult:
        report = compare_pdfs(
            self.work / "source.pdf",
            self.work / "remediated.pdf",
            self.policy,
            diff_dir=self.work / "fidelity",
        )
        report.subject = "remediated.pdf vs source.pdf"
        return self._gate("fidelity", report)

    def _gate(self, name: str, report: Report) -> StageResult:
        failed = exit_status([report], strict=self.record.strict) != 0
        return StageResult(name, "failed" if failed else "passed", report=report)

    def _export(self, name: str, odt: Path, pdf_name: str) -> StageResult:
        if self.executable is None:
            self.executable = find_soffice(self.options.soffice)
            self.record.toolchain["LibreOffice"] = identify_soffice(self.executable).as_dict()
        export_pdfua(
            odt,
            self.work / pdf_name,
            soffice=self.executable,
            timeout=self.options.timeout,
            profile_dir=self.work / "profile",
        )
        return StageResult(name, "passed", gate=False)


def run_pipeline(
    source: str | Path,
    operations: Sequence[Operation],
    policy: FidelityPolicy,
    output_dir: str | Path,
    options: PipelineOptions | None = None,
) -> RunRecord:
    """Audit, remediate, export, validate and compare, then publish an evidence bundle.

    Stages run in a fixed order and stop at the first failed gate; later stages are recorded
    as skipped. The bundle is published whether the run passed or failed.

    Returns
    -------
    RunRecord
        The stage results; ``exit_status`` gives the command exit status.

    """
    options = options or PipelineOptions()
    source, target = Path(source), Path(output_dir)
    require_free_directory(target)
    record = RunRecord(
        input_name=source.name,
        input_sha256=sha256_file(source),
        operations=tuple(operation.as_dict() for operation in operations),
        policy=policy.as_dict(),
        strict=options.strict,
    )
    with tempfile.TemporaryDirectory(prefix="odfa11y-run-") as scratch:
        work = Path(scratch)
        run = _Run(source, work, operations, policy, record, options)
        steps: tuple[Callable[[], StageResult], ...] = (
            run.audit_source,
            run.remediate,
            run.audit_remediated,
            run.export_source,
            run.export_remediated,
            run.audit_pdf,
            run.validate_pdfua,
            run.fidelity,
        )
        for name, step in zip(STAGE_NAMES, steps, strict=True):
            failed = record.failed_stage
            if failed:
                record.stages.append(
                    StageResult(name, "skipped", f"not run: {failed} failed", gate=False)
                )
            else:
                try:
                    record.stages.append(step())
                except (OdfA11yError, OSError) as exc:
                    record.stages.append(StageResult(name, "failed", str(exc), error=True))
        artifacts = {
            path.relative_to(work).as_posix(): path
            for path in sorted(work.rglob("*"))
            if path.is_file() and path.relative_to(work).parts[0] != "profile"
        }
        record.outputs = {name: sha256_file(path) for name, path in artifacts.items()}
        write_bundle(target, record.as_dict(), artifacts)
    return record
