# SPDX-License-Identifier: MPL-2.0
"""Guard document-family native export before entering the application boundary."""

lazy from pathlib import Path

from odfa11y.errors import DocumentRefusal
from odfa11y.families import require_spec
from odfa11y.families.spec import Unsupported
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.native.tools import LibreOffice
from odfa11y.odf import OdfDocument, Use
from odfa11y.odf.export_context import require_native_context
from odfa11y.tool_timeout import Timeout


def native_export_settings(
    document: OdfDocument,
    office: LibreOffice,
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
    return ExportSettings(capability.filter, office, timeout, profile_dir)
