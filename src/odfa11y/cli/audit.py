# SPDX-License-Identifier: MPL-2.0
"""Audit independent inputs and report the effective command gate."""

from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odf
from odfa11y.errors import OdfA11yError, PackageError
from odfa11y.pdf import audit_pdfua, check_pdfua
from odfa11y.report import exit_status, render_reports

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from odfa11y.report import Report

EXECUTION_FAILURE = 3
PDF_MAGIC = b"%PDF"


def is_pdf(path: Path) -> bool:
    """Sniff four bytes from a regular input with a nonblocking descriptor.

    Returns
    -------
    bool
        Whether the input has the PDF signature.

    Raises
    ------
    PackageError
        The selected or opened input is nonregular.

    """
    if not stat.S_ISREG(path.stat().st_mode):
        msg = f"Input {path} must be a regular file (ordinary file aliases are supported)"
        raise PackageError(msg)
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            msg = f"Input {path} must be a regular file"
            raise PackageError(msg)
        return os.read(descriptor, len(PDF_MAGIC)) == PDF_MAGIC
    finally:
        os.close(descriptor)


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
    status = 0
    for source in args.sources:
        try:
            _audit_input(source, args, reports)
        except (OdfA11yError, OSError, ValueError) as exc:
            if args.format == "sarif":
                raise
            print(f"error: Cannot audit {source}: {exc}", file=sys.stderr)
            status = EXECUTION_FAILURE
    if reports:
        print(render_reports(reports, output_format=args.format, source_root=args.source_root))
    status = max(status, exit_status(reports, strict=args.strict))
    command_gate(args, status)
    return status


def command_gate(args: argparse.Namespace, status: int) -> None:
    """Show strict command status separately from the error-only report result."""
    if args.strict:
        outcome = "PASS" if status == 0 else "FAIL"
        print(f"Command gate (--strict): {outcome} (exit {status})", file=sys.stderr)


def _audit_input(source: Path, args: argparse.Namespace, reports: list[Report]) -> None:
    if is_pdf(source):
        reports.append(audit_pdfua(source))
        if args.verapdf or args.verapdf_path:
            report, _result = check_pdfua(source, subject=str(source), executable=args.verapdf_path)
            reports.append(report)
    else:
        reports.append(audit_odf(source, schema=args.schema))
