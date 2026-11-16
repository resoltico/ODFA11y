# SPDX-License-Identifier: MPL-2.0
"""Guard document-family native export before entering the application boundary."""

lazy from pathlib import Path

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.errors import DocumentRefusal
from odfa11y.families import require_spec
from odfa11y.families.spec import Unsupported
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.odf import OdfDocument, Use
from odfa11y.odf.export_context import require_native_context
from odfa11y.progress import ProgressEvent, Step, StepState
from odfa11y.tool_timeout import Timeout
lazy from odfa11y.progress import ProgressObserver


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
    DocumentRefusal
        The family has no native PDF export.

    """
    timeout = Timeout(timeout)
    document.require(Use.EXPORT)
    capability = require_spec(document.kind).export
    if isinstance(capability, Unsupported):
        raise DocumentRefusal(capability.reason)
    require_native_context(document, captured_identity=captured_identity)
    return ExportSettings(capability.filter, soffice, timeout, profile_dir)


def export_document(
    source: str | Path,
    destination: str | Path,
    tools: Tools | None = None,
    *,
    on_progress: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> Path:
    """Export the original document after family selection and native preflight.

    Original exports retain their logical filename/path. This narrow declaration
    guard does not sandbox LibreOffice; callers still own native process isolation.

    Returns
    -------
    Path
        The atomically published PDF path.

    """
    native_tools = native_tools or NativeTools()
    tools = tools or Tools()
    settings = native_export_settings(OdfDocument.open(source), tools.soffice, tools.timeout)
    if on_progress is not None:
        on_progress(ProgressEvent(Step.EXPORT_PDF, StepState.RUNNING))
    result = native_tools.export(Path(source), Path(destination), settings)
    if on_progress is not None:
        on_progress(ProgressEvent(Step.EXPORT_PDF, StepState.PASSED))
    return result
