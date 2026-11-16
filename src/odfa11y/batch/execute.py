# SPDX-License-Identifier: MPL-2.0
"""Execute independent prepared runs and publish immutable batch progress snapshots."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from odfa11y.batch.batch_file import load_manifest, preflight
from odfa11y.batch.record import BatchItemResult, BatchRecord
from odfa11y.errors import Failure, IoFailure, OdfA11yError
from odfa11y.evidence.redact import Redactor
from odfa11y.progress import ProgressObserver, Step, StepState, step
from odfa11y.run.record import RunRecord
lazy from odfa11y.batch.batch_file import BatchItem

type ItemRunner = Callable[[Path, Path, Path, ProgressObserver | None], RunRecord]


def run_batch(
    manifest: str | Path,
    output_dir: str | Path,
    *,
    on_progress: ProgressObserver | None = None,
    runner: ItemRunner,
) -> BatchRecord:
    """Retain completed runs and preparation errors through failure or interruption."""
    manifest, output = Path(manifest), Path(output_dir)
    items = load_manifest(manifest)
    preflight(manifest, output, items)
    record = BatchRecord(tuple(BatchItemResult(item.id) for item in items))
    output.mkdir(parents=True)
    record.publish(output)
    try:
        for index, item in enumerate(items):
            started = replace(record.items[index], _started=True)
            record = _with_item(record, index, started)
            record.publish(output)
            with step(on_progress, Step.BATCH_ITEM, item=item.id) as progress:
                observer = (
                    (lambda event, identity=item.id: on_progress(replace(event, item=identity)))
                    if on_progress
                    else None
                )
                result = _run_item(item, output / item.id, observer, runner)
                record = _with_item(record, index, replace(started, _result=result))
                record.publish(output)
                if result.exit_status:
                    progress.state = StepState.FAILED
    except KeyboardInterrupt:
        record = replace(
            record,
            _interrupted=True,
            items=tuple(
                replace(item, _interrupted=True) if item._started and item._result is None else item
                for item in record.items
            ),
        )
        record.publish(output)
        raise
    record = replace(record, _complete=True)
    record.publish(output)
    return record


def _with_item(record: BatchRecord, index: int, item: BatchItemResult) -> BatchRecord:
    return replace(record, items=(*record.items[:index], item, *record.items[index + 1 :]))


def _run_item(
    item: BatchItem, target: Path, observer: ProgressObserver | None, runner: ItemRunner
) -> RunRecord | Failure:
    try:
        return runner(item.source, item.plan, target, observer)
    except (OdfA11yError, OSError) as exc:
        error = IoFailure.from_oserror(exc) if isinstance(exc, OSError) else exc
        redactor = Redactor.for_locations({
            "source": item.source,
            "plan": item.plan,
            "inputs": item.source.parent,
            "output": target,
        })
        failure = error.as_record()
        remedy = failure.remedy
        if remedy is not None:
            remedy = replace(
                remedy,
                target=redactor.text(remedy.target) if remedy.target else None,
                detail=redactor.text(remedy.detail) if remedy.detail else None,
            )
        return replace(
            failure,
            remedy=remedy,
            message=redactor.text(failure.message),
            details=redactor.text(failure.details),
            problems=tuple(redactor.text(problem) for problem in failure.problems),
        )
