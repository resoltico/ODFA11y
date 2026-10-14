# SPDX-License-Identifier: MPL-2.0
"""Describe the command's actual exit status separately from individual checks."""

from __future__ import annotations


def render_command_outcome(status: int, *, strict: bool = False) -> str:
    """Return a text outcome with the gate policy and actual exit status.

    Returns
    -------
    str
        The command outcome, exit status, reason and gate policy.

    """
    reasons = {
        0: "selected checks completed",
        1: "warnings rejected by the strict gate",
        2: "error findings",
        3: "execution failure; checks may be incomplete",
    }
    outcome = "completed" if status == 0 else "failed"
    policy = "errors and warnings fail" if strict else "errors fail; warnings require review"
    return f"Command: {outcome} (exit {status}; {reasons[status]}).\nGate: {policy}."
