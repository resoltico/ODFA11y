# SPDX-License-Identifier: MPL-2.0
"""Translate stage execution failures without preventing failure evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import OdfA11yError, ToolError
from odfa11y.outcomes import (
    ProgressEvent,
    StageStatus,
    StepName,
    StepState,
    failure_status,
)

from .record import StageResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.outcomes import (
        ProgressObserver,
        StageName,
    )

    from .record import RunRecord

DETAIL_CHARS = 2048


def run_stage(
    name: StageName,
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
        on_progress(ProgressEvent(StepName(name), StepState.RUNNING))
    try:
        return step()
    except (OdfA11yError, OSError) as exc:
        details = getattr(exc, "details", "") if isinstance(exc, ToolError) else ""
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
