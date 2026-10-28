# SPDX-License-Identifier: MPL-2.0
"""Guard document-family native export before entering the application boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odfa11y.content import require_native_context
from odfa11y.errors import UnsupportedKindError
from odfa11y.external_tools import validate_timeout
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument
from odfa11y.outcomes import ProgressEvent, StepName, StepState
from odfa11y.pdf import DEFAULT_TIMEOUT_SECONDS, ExportSettings, export_pdfua

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.outcomes import ProgressObserver


@dataclass(frozen=True, slots=True)
class NativeOptions:
    """Native executable, per-tool time limit and an optional progress observer.

    Observers receive typed ProgressEvent values and must not raise. They are presentation
    hooks, excluded from options identity, and never persisted in reports or evidence.
    """

    soffice: str | Path | None = None
    timeout: int | float = DEFAULT_TIMEOUT_SECONDS
    on_progress: ProgressObserver | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Reject an invalid duration before native work or output creation."""
        validate_timeout(self.timeout)


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
    protection = document.protection
    if protection.inspection_blocked:
        msg = (
            "Encrypted, ambiguous, unsafe or malformed package cannot establish native inspection."
        )
        raise UnsupportedKindError(msg)
    pdf_filter = adapter_for(document.kind).pdf_filter
    if pdf_filter is None:
        kind = document.kind.name if document.kind is not None else "unrecognised"
        msg = f"No PDF export is defined for {kind} documents."
        raise UnsupportedKindError(msg)
    require_native_context(document, captured_identity=captured_identity)
    return ExportSettings(pdf_filter, soffice, timeout, profile_dir)


def export_document(
    source: str | Path, destination: str | Path, options: NativeOptions | None = None
) -> Path:
    """Export the original document after family selection and native preflight.

    Original exports retain their logical filename/path. This narrow declaration
    guard does not sandbox LibreOffice; callers still own native process isolation.

    Returns
    -------
    Path
        The atomically published PDF path.

    """
    options = options or NativeOptions()
    settings = native_export_settings(OdfDocument.open(source), options.soffice, options.timeout)
    if options.on_progress is not None:
        options.on_progress(ProgressEvent(StepName.EXPORT_PDF, StepState.RUNNING))
    result = export_pdfua(source, destination, settings)
    if options.on_progress is not None:
        options.on_progress(ProgressEvent(StepName.EXPORT_PDF, StepState.PASSED))
    return result
