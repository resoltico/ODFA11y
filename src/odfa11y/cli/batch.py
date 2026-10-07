# SPDX-License-Identifier: MPL-2.0
"""Present manifest-driven pipeline execution through the command line."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from odfa11y.batch import run_batch
from odfa11y.pipeline import PipelineOptions

if TYPE_CHECKING:
    import argparse


def batch_command(args: argparse.Namespace) -> int:
    """Run a batch and present path-free progress and evidence references.

    Returns
    -------
    int
        The strongest failure among all entries, or three on interruption.

    """
    options = PipelineOptions(
        profile=args.profile,
        soffice=str(args.soffice) if args.soffice else None,
        verapdf_path=str(args.verapdf_path) if args.verapdf_path else None,
        timeout=args.timeout,
    )
    record = run_batch(args.manifest, args.output_dir, options)
    if args.format == "json":
        text = json.dumps(record.as_dict(), indent=2, sort_keys=True)
    else:
        lines = [f"Batch: {record.status}"]
        lines.extend(
            f"- {item['id']}: {item['status']}; exit={item['exit_status']}; "
            f"evidence={item['evidence']}"
            for item in record.items
        )
        text = "\n".join(lines)
    sys.stdout.write(text + "\n")
    return record.exit_status
