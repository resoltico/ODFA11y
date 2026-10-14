# SPDX-License-Identifier: MPL-2.0
"""Guard document-family native export before entering the application boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odfa11y.content import require_native_context
from odfa11y.errors import UnsupportedKindError
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument
from odfa11y.pdf import DEFAULT_TIMEOUT_SECONDS, ExportSettings, export_pdfua

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class NativeOptions:
    """Native executable, per-tool time limit and an optional progress observer.

    Observers receive fixed labels/statuses and must not raise. They are presentation
    hooks, excluded from options identity, and never persisted in reports or evidence.
    """

    soffice: str | Path | None = None
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    on_progress: Callable[[str, str], None] | None = field(default=None, repr=False, compare=False)


def native_export_settings(
    document: OdfDocument,
    soffice: str | Path | None,
    timeout: int,
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
        options.on_progress("export-pdf", "running")
    result = export_pdfua(source, destination, settings)
    if options.on_progress is not None:
        options.on_progress("export-pdf", "passed")
    return result
