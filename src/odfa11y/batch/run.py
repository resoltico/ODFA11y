# SPDX-License-Identifier: MPL-2.0
"""Run explicit items serially through the ordinary document pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.config import load_config
from odfa11y.errors import OdfA11yError
from odfa11y.evidence import Redactor, write_bundle
from odfa11y.external_tools import termination_interrupt
from odfa11y.pipeline import PipelineOptions, RunRecord, StageResult, run_pipeline

from .manifest import load_manifest, preflight
from .record import BatchRecord

if TYPE_CHECKING:
    from typing import Any

    from .manifest import BatchItem


def run_batch(
    manifest: str | Path, output_dir: str | Path, options: PipelineOptions | None = None
) -> BatchRecord:
    """Run every item, keeping completed evidence through ordinary failures and interruption.

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
                "status": "pending",
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
            for item, progress in zip(items, record.items, strict=True):
                progress["status"] = "running"
                record.publish(output)
                _advance_item(item, progress, output / item.id, options)
                record.publish(output)
        except KeyboardInterrupt:
            for progress in record.items:
                if progress["status"] == "running":
                    progress.update(status="interrupted", exit_status=3)
            record.status = "interrupted"
        else:
            record.status = "failed" if record.exit_status else "completed"
        record.publish(output)
    return record


def _advance_item(
    item: BatchItem, progress: dict[str, Any], target: Path, options: PipelineOptions
) -> None:
    try:
        result = _run_item(item, target, options)
    except OdfA11yError, OSError:
        progress.update(status="failed", exit_status=3, failed_stage="publish-evidence")
        return
    progress.update(
        status="completed" if result.passed else "failed",
        exit_status=result.exit_status,
        failed_stage=result.failed_stage,
        evidence=item.id,
    )


def _run_item(item: BatchItem, target: Path, options: PipelineOptions) -> RunRecord:
    try:
        config = load_config(item.plan)
    except (OdfA11yError, OSError) as exc:
        return _failure(item, target, options, "load-plan", exc)
    try:
        return run_pipeline(item.source, config.operations, config.fidelity, target, options)
    except (OdfA11yError, OSError) as exc:
        return _failure(item, target, options, "pipeline", exc)


def _failure(
    item: BatchItem, target: Path, options: PipelineOptions, stage: str, exc: OdfA11yError | OSError
) -> RunRecord:
    record = RunRecord(
        document={"name": item.id, "sha256": None},
        operations=(),
        policy={},
        profile=options.assurance,
    )
    reason = str(exc) if isinstance(exc, OdfA11yError) else "Item execution could not complete"
    record.stages.append(StageResult(stage, "failed", reason, error=True))
    redactor = Redactor.for_locations({
        "plan": item.plan,
        "inputs": item.plan.parent,
        "source": item.source.parent,
        "output": target,
    })
    write_bundle(target, record.as_dict(), {}, redactor)
    return record
