# SPDX-License-Identifier: MPL-2.0
"""Run explicit items serially through the ordinary document pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.config import load_config
from odfa11y.errors import OdfA11yError
from odfa11y.evidence import Redactor, write_bundle
from odfa11y.external_tools import termination_interrupt
from odfa11y.outcomes import (
    BatchStatus,
    ExitStatus,
    ProgressEvent,
    StageName,
    StageStatus,
    StepName,
    StepState,
    failure_status,
)
from odfa11y.pipeline import PipelineOptions, RunRecord, StageResult, run_pipeline

from .manifest import load_manifest, preflight
from .record import BatchRecord

if TYPE_CHECKING:
    from typing import Any

    from odfa11y.outcomes import (
        ProgressObserver,
    )

    from .manifest import BatchItem


def run_batch(
    manifest: str | Path,
    output_dir: str | Path,
    options: PipelineOptions | None = None,
    *,
    on_progress: ProgressObserver | None = None,
) -> BatchRecord:
    """Run every item, keeping completed evidence through ordinary failures and interruption.

    Progress observers receive fixed batch-step events only and must not raise.

    Returns
    -------
    BatchRecord
        Aggregate exit status and per-item relative evidence references.

    """
    manifest, output = Path(manifest), Path(output_dir)
    options = options or PipelineOptions()
    _ = options.assurance  # Validate the profile before effects.
    items = load_manifest(manifest)
    preflight(manifest, output, items)
    record = BatchRecord(
        items=[
            {
                "id": item.id,
                "status": BatchStatus.PENDING,
                "exit_status": None,
                "failed_stage": None,
                "evidence": None,
            }
            for item in items
        ]
    )
    output.mkdir(parents=True)
    record.publish(output)
    with termination_interrupt():
        try:
            _run_items(items, record, output, options, on_progress)
        except KeyboardInterrupt:
            for progress in record.items:
                if progress["status"] == BatchStatus.RUNNING:
                    progress.update(
                        status=BatchStatus.INTERRUPTED, exit_status=ExitStatus.EXECUTION_FAILURE
                    )
                    if on_progress is not None:
                        on_progress(ProgressEvent(StepName.BATCH_ITEM, StepState.FAILED))
            record.status = BatchStatus.INTERRUPTED
        else:
            record.status = BatchStatus.FAILED if record.exit_status else BatchStatus.COMPLETED
        record.publish(output)
    return record


def _run_items(
    items: tuple[BatchItem, ...],
    record: BatchRecord,
    output: Path,
    options: PipelineOptions,
    on_progress: ProgressObserver | None,
) -> None:
    for item, progress in zip(items, record.items, strict=True):
        progress["status"] = BatchStatus.RUNNING
        record.publish(output)
        if on_progress is not None:
            on_progress(ProgressEvent(StepName.BATCH_ITEM, StepState.RUNNING))
        _advance_item(item, progress, output / item.id, options)
        record.publish(output)
        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    StepName.BATCH_ITEM,
                    StepState.PASSED
                    if progress["status"] == BatchStatus.COMPLETED
                    else StepState.FAILED,
                )
            )


def _advance_item(
    item: BatchItem, progress: dict[str, Any], target: Path, options: PipelineOptions
) -> None:
    try:
        result = _run_item(item, target, options)
    except (OdfA11yError, OSError) as exc:
        progress.update(
            status=BatchStatus.FAILED,
            exit_status=failure_status(exc),
            failed_stage=StageName.PUBLISH_EVIDENCE,
        )
        return
    progress.update(
        status=BatchStatus.COMPLETED if result.passed else BatchStatus.FAILED,
        exit_status=result.exit_status,
        failed_stage=result.failed_stage,
        evidence=item.id,
    )


def _run_item(item: BatchItem, target: Path, options: PipelineOptions) -> RunRecord:
    try:
        config = load_config(item.plan)
    except (OdfA11yError, OSError) as exc:
        return _failure(item, target, options, StageName.LOAD_PLAN, exc)
    try:
        return run_pipeline(item.source, config.operations, config.fidelity, target, options)
    except (OdfA11yError, OSError) as exc:
        return _failure(item, target, options, StageName.PIPELINE, exc)


def _failure(
    item: BatchItem,
    target: Path,
    options: PipelineOptions,
    stage: StageName,
    exc: OdfA11yError | OSError,
) -> RunRecord:
    record = RunRecord(
        document={"name": item.id, "sha256": None},
        operations=(),
        policy={},
        profile=options.assurance,
    )
    reason = str(exc) if isinstance(exc, OdfA11yError) else "Item execution could not complete"
    record.stages.append(
        StageResult(
            stage, StageStatus.FAILED, reason, error=True, failure_status=failure_status(exc)
        )
    )
    redactor = Redactor.for_locations({
        "plan": item.plan,
        "inputs": item.plan.parent,
        "source": item.source.parent,
        "output": target,
    })
    write_bundle(target, record.as_dict(), {}, redactor)
    return record
