# SPDX-License-Identifier: MPL-2.0
"""Exit-code values and their explicit precedence, shared by errors and outcomes."""

from collections.abc import Iterable
from enum import IntEnum


class ExitStatus(IntEnum):
    """Public command outcomes; precedence is independent of numeric values."""

    PASSED = 0
    STRICT_WARNINGS = 1
    ERRORS = 2
    EXECUTION_FAILURE = 3
    USAGE_ERROR = 4

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.PASSED: (
                "The requested checks completed without findings rejected by the selected policy."
            ),
            self.STRICT_WARNINGS: "Warnings prevent acceptance under the strict policy.",
            self.ERRORS: "Errors or a document refusal prevent acceptance.",
            self.EXECUTION_FAILURE: "A tool or operating-system failure prevented completion.",
            self.USAGE_ERROR: (
                "The options, plan or output destination prevent the requested invocation."
            ),
        }[self]


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
