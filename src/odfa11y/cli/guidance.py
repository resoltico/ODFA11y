# SPDX-License-Identifier: MPL-2.0
"""Offer safe next actions for findings and typed command failures."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from odfa11y.audit import template_blockers
from odfa11y.errors import ConfigError, OutputError, ToolNotFoundError
from odfa11y.report import terminal_text

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterable

    from odfa11y.report import Report


def error_hint(args: argparse.Namespace, exc: Exception) -> str | None:
    """Suggest a reversible action using the command's supported interfaces.

    Returns
    -------
    str | None
        A human-facing hint, or None when the specific error already explains recovery.

    """
    if isinstance(exc, ConfigError):
        return (
            "Next: edit the existing configuration and retry. "
            f"Use odfa11y {args.command} --help for command examples; "
            "See https://github.com/resoltico/ODFA11y/blob/main/docs/CONFIGURATION.md "
            "for supported fields."
        )
    if isinstance(exc, OutputError):
        return "Next: choose a new output destination; preserve existing documents and evidence."
    if isinstance(exc, ToolNotFoundError):
        hints = {
            "audit": "install veraPDF on PATH or pass --verapdf-path /path/to/verapdf.",
            "pipeline": "install required tools on PATH; select LibreOffice with --soffice "
            "and veraPDF with --verapdf-path.",
            "batch": "install required tools on PATH; select LibreOffice with --soffice "
            "and veraPDF with --verapdf-path.",
            "doctor": "install LibreOffice and veraPDF on PATH; --soffice selects LibreOffice.",
        }
        return "Next: " + hints.get(
            args.command, "install LibreOffice on PATH or pass --soffice /path/to/soffice."
        )
    return None


def audit_next_step(args: argparse.Namespace, reports: Iterable[Report]) -> str | None:
    """Offer a print-only template command for a readable ODF with open decisions.

    Returns
    -------
    str | None
        A shell-quoted next command when its path can be displayed faithfully.

    """
    if args.format != "text":
        return None
    for report in reports:
        if report.kind != "odf" or not report.sources:
            continue
        if template_blockers(report) is not None:
            continue
        if not any(f.remedy for f in report.findings):
            continue
        source = str(report.sources[0])
        if terminal_text(source) != source:
            continue
        return (
            f"Next: odfa11y template -- {shlex.quote(source)}\n"
            "Review the commented decisions before enabling any remediation."
        )
    return None
