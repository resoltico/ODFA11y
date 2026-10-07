# SPDX-License-Identifier: MPL-2.0
"""Run the whole remediation workflow and publish its evidence."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.audit import BLOCKING_RULE_IDS, audit_odf
from odfa11y.errors import OdfA11yError, PackageError, ToolError
from odfa11y.evidence import Redactor, require_free_directory, sha256_file, write_bundle
from odfa11y.families import GENERIC, adapter_for
from odfa11y.fidelity import compare_pdfs
from odfa11y.odf import OdfDocument, declared_version
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
from odfa11y.remediation import remediate
from odfa11y.report import exit_status

from .profiles import STAGE_NAMES
from .record import PipelineOptions, RunRecord, StageResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.adapter import FamilyAdapter, Operation, ReviewItem
    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.report import Report

DETAIL_CHARS = 2048


@dataclass(slots=True)
class _Run:
    source: Path
    work: Path
    operations: Sequence[Operation]
    policy: FidelityPolicy
    record: RunRecord
    options: PipelineOptions
    adapter: FamilyAdapter = GENERIC
    executable: str | None = None

    # Stage methods raise OdfA11yError or OSError on execution failure; run_pipeline turns
    # either into a failed stage, so no failure can prevent the evidence from being written.

    @property
    def remediated(self) -> Path:
        return self.work / f"remediated{self.source.suffix}"

    def identify_source(self) -> StageResult:
        self.record.document["sha256"] = sha256_file(self.source)
        try:
            document = OdfDocument.open(self.source)
        except PackageError, OSError:
            return StageResult("identify-source", "passed", gate=False)  # audit-source explains
        detection = document.detection
        self.adapter = adapter_for(detection.kind)
        self.record.document.update(
            kind=detection.kind.name if detection.kind else None,
            media_type=detection.media_type,
            layout=document.layout,
            family=detection.kind.family.value if detection.kind else None,
            adapter=self.adapter.name,
            odf_version=declared_version(document),
        )
        self.record.human_review = review_items(self.adapter.review_items)
        return StageResult("identify-source", "passed", gate=False)

    def audit_source(self) -> StageResult:
        report = audit_odf(self.source, schema=True)
        report.subject = self.source.name
        blocked = any(f.rule_id in BLOCKING_RULE_IDS for f in report.findings)
        return StageResult(
            "audit-source",
            "failed" if blocked else "passed",
            "source is not a readable ODF document" if blocked else None,
            report=report,
            gate=blocked,
        )

    def remediate(self) -> StageResult:
        result = remediate(self.source, self.remediated, self.operations)
        return StageResult("remediate", "passed", remediation=result, gate=False)

    def audit_remediated(self) -> StageResult:
        report = audit_odf(self.remediated)
        report.subject = self.remediated.name
        return self._gate("audit-remediated", report)

    def export_source(self) -> StageResult:
        return self._export("export-source", self.source, "source.pdf")

    def export_remediated(self) -> StageResult:
        return self._export("export-remediated", self.remediated, "remediated.pdf")

    def audit_pdf(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf("audit-pdf")
        self.record.fonts = {
            "source": list_fonts(self.work / "source.pdf"),
            "remediated": list_fonts(self.work / "remediated.pdf"),
        }
        report = audit_pdfua(self.work / "remediated.pdf")
        report.subject = "remediated.pdf"
        return self._gate("audit-pdf", report)

    def validate_pdfua(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf("verapdf")
        report, result = check_pdfua(
            self.work / "remediated.pdf",
            subject="remediated.pdf",
            executable=self.options.verapdf_path,
        )
        if result is None:
            required = self.record.profile.verapdf_required
            return StageResult(
                "verapdf", "failed" if required else "skipped", "veraPDF unavailable", report=report
            )
        (self.work / "verapdf.xml").write_text(result.raw_xml, encoding="utf-8")
        self.record.toolchain["veraPDF"] = result.identity.as_dict()
        return self._gate("verapdf", report)

    def fidelity(self) -> StageResult:
        if not self._exportable:
            return self._no_pdf("fidelity")
        report = compare_pdfs(
            self.work / "source.pdf",
            self.work / "remediated.pdf",
            self.policy,
            diff_dir=self.work / "fidelity",
        )
        report.subject = "remediated.pdf vs source.pdf"
        return self._gate("fidelity", report)

    @property
    def _exportable(self) -> bool:
        return self.adapter.pdf_filter is not None

    def _no_pdf(self, name: str) -> StageResult:
        kind = self.record.document.get("kind") or "this kind of"
        reason = f"no PDF export is defined for {kind} documents"
        if self.record.profile.verapdf_required:
            return StageResult(
                name, "failed", f"{reason}; the profile requires PDF validation", error=True
            )
        return StageResult(name, "not-applicable", reason, gate=False)

    def _gate(self, name: str, report: Report) -> StageResult:
        failed = exit_status([report], strict=self.record.strict) != 0
        return StageResult(name, "failed" if failed else "passed", report=report)

    def _export(self, name: str, document: Path, pdf_name: str) -> StageResult:
        if self.adapter.pdf_filter is None:
            return self._no_pdf(name)
        if self.executable is None:
            self.executable = find_soffice(self.options.soffice)
            self.record.toolchain["LibreOffice"] = identify_soffice(self.executable).as_dict()
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
                self.record.toolchain["LibreOffice"]["pdfua_link_descriptions"] = (
                    "supported" if supported else "unsupported"
                )
        export_pdfua(
            document,
            self.work / pdf_name,
            ExportSettings(
                self.adapter.pdf_filter,
                soffice=self.executable,
                timeout=self.options.timeout,
                profile_dir=self.work / "profile",
            ),
        )
        return StageResult(name, "passed", gate=False)


def review_items(items: tuple[ReviewItem, ...]) -> list[dict[str, str]]:
    """Serialize review items for the run record.

    Returns
    -------
    list[dict[str, str]]
        One entry per item with its key and text.

    """
    return [{"key": item.key, "text": item.text} for item in items]


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
    even when the source cannot be read.

    Returns
    -------
    RunRecord
        The stage results; ``exit_status`` gives the command exit status.

    """
    options = options or PipelineOptions()
    profile = options.assurance
    source, target = Path(source), Path(output_dir)
    require_free_directory(target)
    record = RunRecord(
        document={"name": source.name, "sha256": None},
        operations=tuple(operation.as_dict() for operation in operations),
        policy=policy.as_dict(),
        profile=profile,
        human_review=review_items(GENERIC.review_items),
    )
    with tempfile.TemporaryDirectory(prefix="odfa11y-run-") as scratch:
        work = Path(scratch)
        run = _Run(source, work, operations, policy, record, options)
        steps: dict[str, Callable[[], StageResult]] = {
            "identify-source": run.identify_source,
            "audit-source": run.audit_source,
            "remediate": run.remediate,
            "audit-remediated": run.audit_remediated,
            "export-source": run.export_source,
            "export-remediated": run.export_remediated,
            "audit-pdf": run.audit_pdf,
            "verapdf": run.validate_pdfua,
            "fidelity": run.fidelity,
        }
        for name in STAGE_NAMES:
            record.stages.append(_run_stage(name, steps[name], record))
        artifacts = {
            path.relative_to(work).as_posix(): path
            for path in sorted(work.rglob("*"))
            if path.is_file() and path.relative_to(work).parts[0] != "profile"
        }
        record.outputs = {name: sha256_file(path) for name, path in artifacts.items()}
        redactor = Redactor.for_locations({
            "profile": work / "profile",
            "work": work,
            "source": source.parent,
            "output": target,
        })
        write_bundle(target, record.as_dict(), artifacts, redactor)
    return record


def _run_stage(name: str, step: Callable[[], StageResult], record: RunRecord) -> StageResult:
    if name not in record.profile.stages:
        reason = f"not part of the {record.profile.name} profile"
        return StageResult(name, "skipped", reason, gate=False)
    if record.failed_stage:
        return StageResult(name, "skipped", f"not run: {record.failed_stage} failed", gate=False)
    try:
        return step()
    except (OdfA11yError, OSError) as exc:
        details = getattr(exc, "details", "") if isinstance(exc, ToolError) else ""
        return StageResult(
            name,
            "failed",
            _describe(exc),
            error=True,
            details=details[:DETAIL_CHARS] or None,
        )


def _describe(exc: OdfA11yError | OSError) -> str:
    if isinstance(exc, OSError) and not isinstance(exc, OdfA11yError):
        return f"{type(exc).__name__}: {exc.strerror or 'operating-system error'}"
    return str(exc)
