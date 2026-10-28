# SPDX-License-Identifier: MPL-2.0
"""Present pipeline gates, their findings and the retained review evidence."""

from __future__ import annotations

import json
import sys
from textwrap import fill
from typing import TYPE_CHECKING

from odfa11y.config import load_config
from odfa11y.outcomes import StageName
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.report import render_reports, terminal_text

from .outcomes import render_command_outcome
from .progress import progress_callback

if TYPE_CHECKING:
    import argparse

    from odfa11y.pipeline import RunRecord


def pipeline_command(args: argparse.Namespace) -> int:
    """Run the selected assurance profile and present its effective gate outcome.

    Returns
    -------
    int
        The effective pipeline exit status.

    """
    config = load_config(args.config)
    options = PipelineOptions(
        profile=args.profile,
        soffice=str(args.soffice) if args.soffice else None,
        verapdf_path=str(args.verapdf_path) if args.verapdf_path else None,
        timeout=args.timeout,
        on_progress=progress_callback(args.format),
    )
    record = run_pipeline(
        args.source,
        config.operations,
        config.fidelity,
        args.output_dir,
        options,
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
        f"Pipeline profile: {record.profile.name}",
        render_command_outcome(record.exit_status, strict=record.strict),
        f"Evidence: {terminal_text(output_dir)}",
    ]
    for stage in record.stages:
        detail = f" ({terminal_text(stage.reason)})" if stage.reason else ""
        lines.append(
            fill(
                f"- {stage.status:7} {stage.name}{detail}",
                width=80,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
        if stage.details:
            lines.append(
                fill(
                    f"  Tool details: {terminal_text(stage.details)}",
                    width=80,
                    subsequent_indent="  ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    remediated = any(
        stage.name == StageName.AUDIT_REMEDIATED and stage.report for stage in record.stages
    )
    for stage in record.stages:
        if not stage.report or not (stage.report.error_count or stage.report.warning_count):
            continue
        if not stage.gate and (stage.name != StageName.AUDIT_SOURCE or remediated):
            continue
        label = "Before remediation" if not stage.gate else "Gate findings"
        lines.extend(["", f"{label}: {stage.name}", render_reports([stage.report])])
    lines.extend([
        "",
        "Scope: selected automated checks; human review is still required.",
        f"Review: {terminal_text(output_dir)}/REVIEW.md",
    ])
    return "\n".join(lines)
