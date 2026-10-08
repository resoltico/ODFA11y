# SPDX-License-Identifier: MPL-2.0
"""Translate stage execution failures without preventing failure evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import OdfA11yError, ToolError

from .record import StageResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from .record import RunRecord

DETAIL_CHARS = 2048


def run_stage(name: str, step: Callable[[], StageResult], record: RunRecord) -> StageResult:
    """Execute an eligible stage, retaining controlled failure details.

    Returns
    -------
    StageResult
        A passed, failed or skipped stage.

    """
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
