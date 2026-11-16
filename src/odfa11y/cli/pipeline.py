# SPDX-License-Identifier: MPL-2.0
"""Present pipeline gates, their findings and the retained review evidence."""

import json
import sys
from textwrap import fill
lazy import argparse

import odfa11y as api
from odfa11y import render_reports, terminal_text
lazy from odfa11y import RunRecord

from .outcomes import render_command_outcome
from .progress import progress_callback


def pipeline_command(args: argparse.Namespace) -> int:
    """Run the selected assurance profile and present its effective gate outcome.

    Returns
    -------
    int
        The effective pipeline exit status.

    """
    record = api.run(
        args.source,
        args.plan,
        args.output_dir,
        tools=api.Tools(args.soffice, args.verapdf, args.timeout),
        profile=args.profile,
        observer=progress_callback(args.format),
        native_tools=args.native_tools,
    )
    if args.format == "json":
        sys.stdout.write(json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(_render_pipeline(record, args.output_dir) + "\n")
    return record.exit_status


def _render_pipeline(record: RunRecord, output_dir: object) -> str:
    """Describe the gates and findings without claiming completed human review.

    Returns
    -------
    str
        The human pipeline summary and references to its retained evidence.

    """
    lines = [
        f"Pipeline profile: {record.profile.value}",
        render_command_outcome(record.exit_status, strict=record.strict),
        f"Evidence: {terminal_text(output_dir)}",
    ]
    for stage in record.stages:
        lines.append(f"- {stage.outcome.status:14} {stage.name}")
        if isinstance(stage.outcome, api.Refused | api.Crashed):
            lines.append(fill(terminal_text(str(stage.outcome.error)), width=80))
            if stage.outcome.error.details:
                lines.append("Tool details: " + terminal_text(stage.outcome.error.details))
        if stage.report and (stage.report.error_count or stage.report.warning_count):
            lines.extend(["", f"Findings: {stage.name}", render_reports([stage.report])])
    lines.extend([
        "",
        "Scope: selected automated checks; human review is still required.",
        f"Review: {terminal_text(output_dir)}/REVIEW.md",
    ])
    return "\n".join(lines)
