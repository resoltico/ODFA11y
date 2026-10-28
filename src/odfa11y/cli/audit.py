# SPDX-License-Identifier: MPL-2.0
"""Audit independent inputs and report the effective command gate."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from odfa11y.errors import OdfA11yError
from odfa11y.outcomes import ExitStatus, combine_statuses, failure_status
from odfa11y.pipeline import audit_document
from odfa11y.report import exit_status, render_reports, terminal_text

from .guidance import audit_next_step
from .outcomes import render_command_outcome
from .progress import progress_callback

if TYPE_CHECKING:
    import argparse

    from odfa11y.report import Report


def audit_command(args: argparse.Namespace) -> int:
    """Retain successful audits and continue after text/JSON input failures.

    Returns
    -------
    int
        The strongest command status across every input.

    Raises
    ------
    OdfA11yError
        A SARIF inspection fails; no partial log is emitted.
    OSError
        A SARIF input cannot be read.
    ValueError
        SARIF identity or rendering is invalid.

    """
    reports: list[Report] = []
    status = ExitStatus.PASSED
    for source in args.sources:
        try:
            reports.extend(
                audit_document(
                    source,
                    schema=args.schema,
                    verapdf=args.verapdf,
                    verapdf_path=args.verapdf_path,
                    timeout=args.timeout,
                    on_progress=progress_callback(args.format),
                )
            )
        except (OdfA11yError, OSError, ValueError) as exc:
            if args.format == "sarif":
                raise
            print(  # noqa: T201  CLI output is the command interface.
                f"error: Cannot audit {terminal_text(source)}: {terminal_text(exc)}",
                file=sys.stderr,
            )
            status = combine_statuses([status, failure_status(exc)])
    status = combine_statuses([status, exit_status(reports, strict=args.strict)])
    command_gate(args, status)
    if reports:
        print(render_reports(reports, output_format=args.format, source_root=args.source_root))  # noqa: T201  CLI output is the command interface.
    if args.format == "text" and (next_step := audit_next_step(args, reports)):
        print(next_step)  # noqa: T201  CLI output is the command interface.
    return status


def command_gate(
    args: argparse.Namespace,
    status: int,
    *,
    scope: str = "selected automated checks; human review is still required.",
) -> None:
    """Show the actual text outcome while retaining machine-format stderr contracts."""
    if args.format == "text":
        print(render_command_outcome(status, strict=args.strict))  # noqa: T201  CLI output is the command interface.
        print(f"Scope: {terminal_text(scope)}")  # noqa: T201  CLI output is the command interface.
    elif args.strict:
        outcome = "PASS" if status == 0 else "FAIL"
        print(f"Command gate (--strict): {outcome} (exit {status})", file=sys.stderr)  # noqa: T201  CLI output is the command interface.
