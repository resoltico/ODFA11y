# SPDX-License-Identifier: MPL-2.0
"""Append terminal-only progress without contaminating machine output."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from odfa11y.report import terminal_text

if TYPE_CHECKING:
    from collections.abc import Callable


def progress_callback(output_format: str) -> Callable[[str, str], None] | None:
    """Create a plain stderr observer for text commands with an interactive terminal.

    A closed or failing progress stream disables only progress. Callbacks must not
    raise other exceptions: programming failures and interruption remain visible.

    Returns
    -------
    Callable[[str, str], None] | None
        A label/status observer, or None for redirected stderr and machine output.

    """
    stream = sys.stderr
    if output_format != "text" or not stream.isatty():
        return None
    enabled = True

    def emit(label: str, status: str) -> None:
        nonlocal enabled
        if enabled:
            try:
                stream.write(f"Progress: {terminal_text(label)}: {terminal_text(status)}\n")
                stream.flush()
            except OSError:
                enabled = False

    return emit
