# SPDX-License-Identifier: MPL-2.0
"""Append terminal-only progress without contaminating machine output."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from odfa11y import StepName, terminal_text

if TYPE_CHECKING:
    from odfa11y import ProgressEvent, ProgressObserver


_LABELS = {
    StepName.IDENTIFY_SOURCE: "Identify source",
    StepName.AUDIT_SOURCE: "Audit source",
    StepName.REMEDIATE: "Apply reviewed decisions",
    StepName.AUDIT_REMEDIATED: "Audit remediated source",
    StepName.EXPORT_SOURCE: "Export source PDF",
    StepName.EXPORT_REMEDIATED: "Export remediated PDF",
    StepName.AUDIT_PDF: "Inspect PDF",
    StepName.VALIDATE_PDF: "Validate PDF/UA",
    StepName.FIDELITY: "Compare fidelity",
    StepName.PUBLISH_EVIDENCE: "Publish evidence",
    StepName.LOAD_PLAN: "Load reviewed plan",
    StepName.PIPELINE: "Run assurance workflow",
    StepName.AUDIT_DOCUMENT: "Audit document",
    StepName.EXPORT_PDF: "Export PDF",
    StepName.EXPORT_CANDIDATE: "Export candidate PDF",
    StepName.COMPARE_FIDELITY: "Compare fidelity",
    StepName.PROBE_CAPABILITIES: "Measure native capabilities",
    StepName.PROBE_TOOLCHAIN: "Inspect tools",
    StepName.BATCH_ITEM: "Process batch item",
}


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
                label = _LABELS[event.step]
                stream.write(f"Progress: {terminal_text(label)}: {terminal_text(event.state)}\n")
                stream.flush()
            except OSError:
                enabled = False

    return emit
