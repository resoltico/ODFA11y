# SPDX-License-Identifier: MPL-2.0
"""Append terminal-only progress without contaminating machine output."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from odfa11y.report import terminal_text

if TYPE_CHECKING:
    from odfa11y.outcomes import ProgressEvent, ProgressObserver


def progress_callback(output_format: str) -> ProgressObserver | None:
    """Create a plain stderr observer for text commands with an interactive terminal.

    A closed or failing progress stream disables only progress. Callbacks must not
    raise other exceptions: programming failures and interruption remain visible.

    Returns
    -------
    ProgressObserver | None
        A typed progress-event observer, or None for redirected stderr and machine output.

    """
    stream = sys.stderr
    if output_format != "text" or not stream.isatty():
        return None
    enabled = True

    def emit(event: ProgressEvent) -> None:
        nonlocal enabled
        if enabled:
            try:
                label = event.step.value.replace("-", " ").capitalize()
                stream.write(f"Progress: {terminal_text(label)}: {terminal_text(event.state)}\n")
                stream.flush()
            except OSError:
                enabled = False

    return emit
