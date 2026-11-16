# SPDX-License-Identifier: MPL-2.0
"""Acquire bounded veraPDF XML without interpreting PDF validation semantics."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from odfa11y.errors import ToolFailure
from odfa11y.native.process import find_executable, run_bounded, validate_timeout


@dataclass(frozen=True, slots=True)
class ValidationOutput:
    xml: bytes
    diagnostics: str


def find_verapdf(requested: str | Path | None = None) -> str:
    """Locate the veraPDF executable.

    Returns
    -------
    str
        The executable path.

    """
    return find_executable(requested, ("verapdf",))


def run_verapdf(
    pdf: str | Path,
    *,
    executable: str | Path | None = None,
    flavour: str = "ua1",
    timeout: float,
    max_report_bytes: int,
) -> ValidationOutput:
    """Run the selected validator and return bounded XML output and diagnostics.

    Interpretation of a completed report belongs to the caller, including noncompliance
    reports returned with a nonzero process status.
    """
    validate_timeout(timeout)
    command = [
        find_verapdf(executable),
        "-f",
        flavour,
        "--format",
        "xml",
        "--loglevel",
        "0",
        str(Path(pdf).resolve()),
    ]
    try:
        completed = run_bounded(command, timeout=timeout, max_output=max_report_bytes)
    except subprocess.TimeoutExpired as exc:
        msg = f"veraPDF timed out after {timeout} s"
        raise ToolFailure(msg) from exc
    if completed.stdout_truncated:
        msg = f"veraPDF output exceeded {max_report_bytes} bytes"
        raise ToolFailure(msg)
    if completed.returncode != 0 and not completed.stdout.strip():
        msg = f"veraPDF failed (exit status {completed.returncode})."
        raise ToolFailure(msg, details=completed.stderr.strip())
    return ValidationOutput(completed.stdout.encode("utf-8"), completed.stderr)
