# SPDX-License-Identifier: MPL-2.0
"""Present document style usage and effective spacing in readable or machine form."""

from __future__ import annotations

import json
import sys
import textwrap
from typing import TYPE_CHECKING

from odfa11y.families import style_usage
from odfa11y.report import terminal_text

if TYPE_CHECKING:
    import argparse


def styles_command(args: argparse.Namespace) -> int:
    """Report styles without changing their identities or machine representation.

    Returns
    -------
    int
        Zero after presenting the supported style report.

    """
    rows = style_usage(args.source)
    if args.format == "json":
        sys.stdout.write(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        return 0
    lines = [f"Paragraph styles in {terminal_text(args.source)}:"]
    if not rows:
        lines.append("No paragraph styles were found.")
    for row in rows:
        lines.extend([
            f"- {terminal_text(row['style'])}: {row['count']} use(s)",
            f"  Parent: {terminal_text(row['parent']) if row['parent'] else 'none'}",
        ])
        spacing = "; ".join(
            f"{terminal_text(key)}={terminal_text(value)}" for key, value in row["spacing"].items()
        )
        lines.append(
            textwrap.fill(
                f"  Spacing: {spacing or 'not declared'}",
                width=80,
                subsequent_indent="    ",
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0
