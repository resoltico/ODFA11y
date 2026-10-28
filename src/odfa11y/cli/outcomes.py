# SPDX-License-Identifier: MPL-2.0
"""Describe the command's actual exit status separately from individual checks."""

from __future__ import annotations

from odfa11y import ExitStatus


def render_command_outcome(status: int, *, strict: bool = False) -> str:
    """Return a text outcome with the gate policy and actual exit status.

    Returns
    -------
    str
        The command outcome, exit status, reason and gate policy.

    """
    reasons = {
        ExitStatus.PASSED: "selected checks completed",
        ExitStatus.STRICT_WARNINGS: "warnings rejected by the strict gate",
        ExitStatus.ERRORS: "error findings",
        ExitStatus.EXECUTION_FAILURE: "execution failure; checks may be incomplete",
        ExitStatus.USAGE_ERROR: "invalid arguments, plan or policy",
    }
    outcome = "completed" if status == 0 else "failed"
    policy = "errors and warnings fail" if strict else "errors fail; warnings require review"
    return f"Command: {outcome} (exit {status}; {reasons[ExitStatus(status)]}).\nGate: {policy}."
