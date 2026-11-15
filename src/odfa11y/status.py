# SPDX-License-Identifier: MPL-2.0
"""status vocabulary."""

from enum import IntEnum, StrEnum
lazy from collections.abc import Iterable

from odfa11y.errors import UsageError


class ExitStatus(IntEnum):
    """Public command outcomes; precedence is independent of numeric values."""

    PASSED = 0
    STRICT_WARNINGS = 1
    ERRORS = 2
    EXECUTION_FAILURE = 3
    USAGE_ERROR = 4


EXIT_PRECEDENCE = (
    ExitStatus.PASSED,
    ExitStatus.STRICT_WARNINGS,
    ExitStatus.ERRORS,
    ExitStatus.USAGE_ERROR,
    ExitStatus.EXECUTION_FAILURE,
)


def combine_statuses(statuses: Iterable[ExitStatus | int]) -> ExitStatus:
    """Combine outcomes by their explicit public precedence.

    Returns
    -------
    ExitStatus
        The strongest outcome, or passed for empty input.

    """
    present = {ExitStatus(status) for status in statuses}
    return next(
        (status for status in reversed(EXIT_PRECEDENCE) if status in present), ExitStatus.PASSED
    )


def failure_status(error: BaseException) -> ExitStatus:
    """Classify an expected input error separately from execution failure.

    Returns
    -------
    ExitStatus
        Usage error for invalid arguments/plans, execution failure otherwise.

    """
    return ExitStatus.USAGE_ERROR if isinstance(error, UsageError) else ExitStatus.EXECUTION_FAILURE


class StageStatus(StrEnum):
    """The outcome or applicability of one pipeline stage."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not-applicable"


class RunStatus(StrEnum):
    """Overall pipeline assurance result."""

    PASSED = StageStatus.PASSED
    FAILED = StageStatus.FAILED


class BatchStatus(StrEnum):
    """Execution lifetime of a batch or one manifest item."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
