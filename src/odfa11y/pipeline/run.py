# SPDX-License-Identifier: MPL-2.0
"""Run the whole remediation workflow and publish its evidence."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odt
from odfa11y.errors import OdfA11yError, ToolNotFoundError
from odfa11y.evidence import require_free_directory, sha256_file, write_bundle
from odfa11y.fidelity import compare_pdfs
from odfa11y.pdf import (
    add_verapdf_findings,
    audit_pdfua,
    export_pdfua,
    find_soffice,
    find_verapdf,
    identify_soffice,
    validate_pdfua,
)
from odfa11y.remediation import remediate
from odfa11y.report import Report, exit_status, rules

from .record import STAGE_NAMES, PipelineOptions, RunRecord, StageResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.remediation import Operation


@dataclass(slots=True)
class _Run:
    source: Path
    work: Path
    operations: Sequence[Operation]
    policy: FidelityPolicy
    record: RunRecord
    options: PipelineOptions
    executable: str | None = None

    @property
    def profile(self) -> Path:
        return self.work / "profile"

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
        try:
            result = remediate(self.source, self.work / "remediated.odt", self.operations)
        except OdfA11yError as exc:
            return StageResult("remediate", "failed", str(exc), error=True)
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
        if self.options.verapdf is None:
            return StageResult("verapdf", "skipped", "not requested", gate=False)
        report = Report(kind="verapdf", subject="remediated.pdf")
        try:
            executable = find_verapdf(
                None if self.options.verapdf == "auto" else self.options.verapdf
            )
        except ToolNotFoundError as exc:
            report.add(rules.VERA000, str(exc))
            failed = self.record.strict
            return StageResult(
                "verapdf", "failed" if failed else "skipped", "veraPDF unavailable", report=report
            )
        try:
            result = validate_pdfua(self.work / "remediated.pdf", executable=executable)
        except OdfA11yError as exc:
            return StageResult("verapdf", "failed", str(exc), error=True)
        add_verapdf_findings(report, result)
        (self.work / "verapdf.xml").write_text(result.raw_xml, encoding="utf-8")
        self.record.toolchain["veraPDF"] = result.identity.as_dict()
        return self._gate("verapdf", report)

    def fidelity(self) -> StageResult:
        try:
            report = compare_pdfs(
                self.work / "source.pdf",
                self.work / "remediated.pdf",
                self.policy,
                diff_dir=self.work / "fidelity",
            )
        except OdfA11yError as exc:
            return StageResult("fidelity", "failed", str(exc), error=True)
        report.subject = "remediated.pdf vs source.pdf"
        return self._gate("fidelity", report)

    def _gate(self, name: str, report: Report) -> StageResult:
        failed = exit_status([report], strict=self.record.strict) != 0
        return StageResult(name, "failed" if failed else "passed", report=report)

    def _export(self, name: str, odt: Path, pdf_name: str) -> StageResult:
        try:
            if self.executable is None:
                self.executable = find_soffice(self.options.soffice)
                self.record.toolchain["LibreOffice"] = identify_soffice(self.executable).as_dict()
            export_pdfua(
                odt,
                self.work / pdf_name,
                soffice=self.executable,
                timeout=self.options.timeout,
                profile_dir=self.profile,
            )
        except OdfA11yError as exc:
            return StageResult(name, "failed", str(exc), error=True)
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
                record.stages.append(step())
        artifacts = {
            path.relative_to(work).as_posix(): path
            for path in sorted(work.rglob("*"))
            if path.is_file() and path.relative_to(work).parts[0] != "profile"
        }
        record.outputs = {name: sha256_file(path) for name, path in artifacts.items()}
        write_bundle(target, record.as_dict(), artifacts)
    return record
