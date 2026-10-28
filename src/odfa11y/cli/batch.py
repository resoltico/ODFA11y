# SPDX-License-Identifier: MPL-2.0
"""Present manifest-driven pipeline execution through the command line."""

from __future__ import annotations

import json
import sys
import textwrap
from typing import TYPE_CHECKING

import odfa11y as api
from odfa11y import terminal_text

from .progress import progress_callback

if TYPE_CHECKING:
    import argparse


def batch_command(args: argparse.Namespace) -> int:
    """Run a batch and present path-free progress and evidence references.

    Returns
    -------
    int
        The strongest failure among all entries, or three on interruption.

    """
    record = api.run_batch(
        args.manifest,
        args.output_dir,
        tools=api.Tools(args.soffice, args.verapdf_path, args.timeout),
        profile=args.profile,
        observer=progress_callback(args.format),
        rebind=args.rebind,
    )
    if args.format == "json":
        text = json.dumps(record.as_dict(), indent=2, sort_keys=True)
    else:
        lines = [
            f"Batch: {record.status}",
            f"Profile: {args.profile}; exit {record.exit_status}",
        ]
        lines.extend(
            f"- {item.id}: {item.status}; exit={item.exit_status}; "
            f"failed_stage={item.failed_stage}; evidence={item.evidence}"
            for item in record.items
        )
        text = "\n".join(
            textwrap.fill(
                terminal_text(line),
                width=80,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
            for line in lines
        )
    sys.stdout.write(text + "\n")
    return record.exit_status
