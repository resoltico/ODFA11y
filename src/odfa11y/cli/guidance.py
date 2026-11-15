# SPDX-License-Identifier: MPL-2.0
"""Offer safe next actions for findings and typed command failures."""

import shlex
lazy import argparse
lazy from collections.abc import Iterable

from odfa11y import OdfA11yError, Remedy, RemedyAction, plan_blockers, terminal_text
lazy from odfa11y import Report


def error_hint(args: argparse.Namespace, exc: Exception) -> str | None:
    """Suggest a reversible action using the command's supported interfaces.

    Returns
    -------
    str | None
        A human-facing hint, or None when the specific error already explains recovery.

    """
    if not isinstance(exc, OdfA11yError) or exc.remedy is None:
        return None
    return remedy_hint(exc.remedy)


def remedy_hint(remedy: Remedy) -> str | None:
    """Render the producer-owned next action for an error or refused edit."""
    target = terminal_text(remedy.target or "the document")
    detail = terminal_text(remedy.detail or "the declared resource")
    match remedy.action:
        case RemedyAction.REGENERATE_PLAN:
            return "Next: generate a fresh plan for this source and review its answers."
        case RemedyAction.REBIND_PLAN:
            return (
                "Next: use plan NEW_SOURCE --from OLD_PLAN and review answers that no longer match."
            )
        case RemedyAction.CHOOSE_OUTPUT:
            return (
                "Next: choose a new output destination; preserve existing documents and evidence."
            )
        case RemedyAction.INSTALL_TOOL:
            tool = terminal_text(remedy.target or "the required native tool")
            return f"Next: install or select {tool}."
        case RemedyAction.EMBED_RESOURCE:
            return f"Next: embed {detail} for {target} in the source application."
        case RemedyAction.EDIT_IN_APPLICATION:
            instruction = terminal_text(remedy.detail or "")
            return f"Next: edit {target} in the source application. {instruction}".rstrip()


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
        if plan_blockers(report) is not None:
            continue
        if not report.decisions:
            continue
        source = str(report.sources[0])
        if terminal_text(source) != source:
            continue
        return (
            f"Next: odfa11y plan -- {shlex.quote(source)}\n"
            "Review the commented decisions before enabling any remediation."
        )
    return None
