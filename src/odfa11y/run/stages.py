# SPDX-License-Identifier: MPL-2.0
"""Translate stage execution failures without preventing failure evidence."""

lazy from collections.abc import Callable

from odfa11y.errors import OdfA11yError
from odfa11y.progress import ProgressEvent, Step, StepState
from odfa11y.run.record import StageResult
from odfa11y.status import StageStatus, failure_status
lazy from odfa11y.progress import ProgressObserver, Stage
lazy from odfa11y.run.record import RunRecord

DETAIL_CHARS = 2048


def run_stage(
    name: Stage,
    step: Callable[[], StageResult],
    record: RunRecord,
    *,
    on_progress: ProgressObserver | None = None,
) -> StageResult:
    """Execute an eligible stage, retaining controlled failure details.

    Returns
    -------
    StageResult
        A passed, failed or skipped stage.

    """
    if name not in record.profile.stages:
        reason = f"not part of the {record.profile.name} profile"
        return StageResult(name, StageStatus.SKIPPED, reason, gate=False)
    if record.failed_stage:
        return StageResult(
            name, StageStatus.SKIPPED, f"not run: {record.failed_stage} failed", gate=False
        )
    if on_progress is not None:
        on_progress(ProgressEvent(Step(name), StepState.RUNNING))
    try:
        return step()
    except (OdfA11yError, OSError) as exc:
        details = getattr(exc, "details", "") if isinstance(exc, OdfA11yError) else ""
        return StageResult(
            name,
            StageStatus.FAILED,
            _describe(exc),
            error=True,
            failure_status=failure_status(exc),
            details=details[:DETAIL_CHARS] or None,
        )


def _describe(exc: OdfA11yError | OSError) -> str:
    if isinstance(exc, OSError) and not isinstance(exc, OdfA11yError):
        return f"{type(exc).__name__}: {exc.strerror or 'operating-system error'}"
    return str(exc)
