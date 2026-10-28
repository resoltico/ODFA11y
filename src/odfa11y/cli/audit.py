# SPDX-License-Identifier: MPL-2.0
"""Audit independent inputs and report the effective command gate."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import odfa11y as api
from odfa11y import terminal_text

from .guidance import audit_next_step
from .outcomes import render_command_outcome
from .progress import progress_callback

if TYPE_CHECKING:
    import argparse


def audit_command(args: argparse.Namespace) -> int:
    """Retain successful audits and continue after text/JSON input failures.

    Returns
    -------
    int
        The strongest command status across every input.

    """
    result = api.audit(
        args.sources,
        tools=api.Tools(verapdf=args.verapdf_path, timeout=args.timeout),
        schema=args.schema,
        validate_pdf=args.verapdf,
        strict=args.strict,
        observer=progress_callback(args.format),
    )
    rendered = result.render(args.format, source_root=args.source_root)
    for item in result.failures:
        sys.stderr.write(
            f"error: Cannot audit {terminal_text(item.source)}: {terminal_text(item.error)}\n"
        )
    command_gate(args, result.exit_status)
    if rendered is not None:
        print(rendered)  # noqa: T201  CLI output.
    if args.format == "text" and (next_step := audit_next_step(args, result.reports)):
        print(next_step)  # noqa: T201  CLI output.
    return result.exit_status


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
