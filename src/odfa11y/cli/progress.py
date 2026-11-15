# SPDX-License-Identifier: MPL-2.0
"""Append terminal-only progress without contaminating machine output."""

import sys

from odfa11y import Step, terminal_text
lazy from odfa11y import ProgressEvent, ProgressObserver

_LABELS = {
    Step.IDENTIFY_SOURCE: "Identify source",
    Step.AUDIT_SOURCE: "Audit source",
    Step.REMEDIATE: "Apply reviewed decisions",
    Step.AUDIT_REMEDIATED: "Audit remediated source",
    Step.EXPORT_SOURCE: "Export source PDF",
    Step.EXPORT_REMEDIATED: "Export remediated PDF",
    Step.AUDIT_PDF: "Inspect PDF",
    Step.VALIDATE_PDF: "Validate PDF/UA",
    Step.FIDELITY: "Compare fidelity",
    Step.PUBLISH_EVIDENCE: "Publish evidence",
    Step.LOAD_PLAN: "Load reviewed plan",
    Step.PIPELINE: "Run assurance workflow",
    Step.AUDIT_DOCUMENT: "Audit document",
    Step.EXPORT_PDF: "Export PDF",
    Step.EXPORT_CANDIDATE: "Export candidate PDF",
    Step.COMPARE_FIDELITY: "Compare fidelity",
    Step.PROBE_CAPABILITIES: "Measure native capabilities",
    Step.PROBE_TOOLCHAIN: "Inspect tools",
    Step.BATCH_ITEM: "Process batch item",
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
