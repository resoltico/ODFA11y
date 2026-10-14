# SPDX-License-Identifier: MPL-2.0
"""Executable public API examples; run against an installed wheel outside the checkout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.audit import prepare_template
from odfa11y.evidence import check_bundle
from odfa11y.families import style_usage
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import (
    PipelineOptions,
    audit_document,
    compare_documents,
    export_document,
    inspect_tools,
    run_pipeline,
)
from odfa11y.remediation import SetMetadata, remediate
from odfa11y.report import exit_status

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.pipeline import NativeOptions, RunRecord
    from odfa11y.report import Report


def inspect_source(source: Path, work: Path) -> list[Report]:
    """Audit incrementally, inspect styles, prepare decisions and publish a reviewed edit.

    Returns
    -------
    list[Report]
        Completed reports; strict warning policy remains the caller's choice.

    """
    work.mkdir(parents=True, exist_ok=True)
    completed = []
    for report in audit_document(source, schema=True):
        completed.append(report)
        # Core operations produce no terminal output. Render or serialize when needed.
        report.as_dict()
    style_usage(source)
    report, template = prepare_template(source)
    completed.append(report)
    if template is not None:
        (work / "decisions.toml").write_text(template, encoding="utf-8")
    # This title is an explicit example decision, never inferred from document content.
    remediate(source, work / ("reviewed" + source.suffix), [SetMetadata(title="Reviewed example")])
    exit_status(completed, strict=True)
    return completed


def native_work(
    source: Path, work: Path, options: NativeOptions
) -> tuple[Report, RunRecord, list[str]]:
    """Export, compare and publish evidence while retaining each independent result.

    Returns
    -------
    tuple[Report, RunRecord, list[str]]
        Fidelity, pipeline stages/gates and bundle integrity problems. Inspect all three;
        successful integrity alone never means the document passed accessibility gates.

    """
    work.mkdir(parents=True, exist_ok=True)
    _identities, probe_error = inspect_tools(options)
    # The partial facts remain available even when the controlled probe error is raised.
    if probe_error is not None:
        raise probe_error
    pdf = export_document(source, work / "publication.pdf", options)
    comparison = compare_documents(source, pdf, FidelityPolicy(), work / "diff", options)
    record = run_pipeline(
        source,
        [SetMetadata(title="Reviewed example")],
        FidelityPolicy(),
        work / "evidence",
        PipelineOptions(
            soffice=str(options.soffice) if options.soffice is not None else None,
            timeout=options.timeout,
        ),
    )
    # A failed gate still leaves evidence. Integrity says nothing about accessibility.
    problems = check_bundle(work / "evidence")
    return comparison, record, problems
