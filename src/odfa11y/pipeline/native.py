# SPDX-License-Identifier: MPL-2.0
"""Guard document-family native export before entering the application boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import UnsupportedKindError
from odfa11y.families import adapter_for
from odfa11y.native.export import ExportSettings, export_pdfua
from odfa11y.native.export_context import require_native_context
from odfa11y.native.process import validate_timeout
from odfa11y.odf import OdfDocument, Use
from odfa11y.outcomes import ProgressEvent, StepName, StepState
from odfa11y.tools import Tools

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.outcomes import ProgressObserver


def native_export_settings(
    document: OdfDocument,
    soffice: str | Path | None,
    timeout: float,
    profile_dir: str | Path | None = None,
    *,
    captured_identity: bool = False,
) -> ExportSettings:
    """Select the family's filter and establish its native resource contract.

    Returns
    -------
    ExportSettings
        Settings for the guarded document and the caller-owned optional profile.

    Raises
    ------
    UnsupportedKindError
        The family has no native PDF export.

    """
    validate_timeout(timeout)
    document.require(Use.EXPORT)
    pdf_filter = adapter_for(document.kind).pdf_filter
    if pdf_filter is None:
        kind = document.kind.name if document.kind is not None else "unrecognised"
        msg = f"No PDF export is defined for {kind} documents."
        raise UnsupportedKindError(msg)
    require_native_context(document, captured_identity=captured_identity)
    return ExportSettings(pdf_filter, soffice, timeout, profile_dir)


def export_document(
    source: str | Path,
    destination: str | Path,
    tools: Tools | None = None,
    *,
    on_progress: ProgressObserver | None = None,
) -> Path:
    """Export the original document after family selection and native preflight.

    Original exports retain their logical filename/path. This narrow declaration
    guard does not sandbox LibreOffice; callers still own native process isolation.

    Returns
    -------
    Path
        The atomically published PDF path.

    """
    tools = tools or Tools()
    settings = native_export_settings(OdfDocument.open(source), tools.soffice, tools.timeout)
    if on_progress is not None:
        on_progress(ProgressEvent(StepName.EXPORT_PDF, StepState.RUNNING))
    result = export_pdfua(source, destination, settings)
    if on_progress is not None:
        on_progress(ProgressEvent(StepName.EXPORT_PDF, StepState.PASSED))
    return result
