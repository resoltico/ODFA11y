# SPDX-License-Identifier: MPL-2.0
"""Capture an original document and explicitly publish its guarded native export."""

import shutil
import tempfile
from pathlib import Path

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit.export import native_export_settings
from odfa11y.capture import capture_source
from odfa11y.errors import IoFailure
from odfa11y.odf import OdfDocument
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.publish import publish_file, require_distinct, require_file_destination


def export_document(
    source: str | Path,
    destination: str | Path,
    tools: Tools | None = None,
    *,
    replace: bool = False,
    on_progress: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> Path:
    """Capture and parse once, resolve LibreOffice once, and publish with explicit replacement."""
    source, destination = Path(source), Path(destination)
    operations = native_tools or NativeTools()
    try:
        require_distinct(source, destination)
        require_file_destination(destination, replace=replace)
        with (
            capture_source(source) as captured,
            tempfile.TemporaryDirectory(prefix="odfa11y-export-") as scratch,
        ):
            document = OdfDocument.open(captured.path)
            resolved = (tools or Tools()).resolve(libreoffice=True, native_tools=operations)
            office = resolved.libreoffice
            if office is None:
                message = "Export preparation did not resolve LibreOffice"
                raise ValueError(message)
            settings = native_export_settings(
                document, office, resolved.timeout, captured_identity=True
            )
            staged = Path(scratch) / "export.pdf"
            with step(on_progress, Step.EXPORT_PDF):
                operations.export(captured.path, staged, settings)

                def write(stream) -> None:
                    with staged.open("rb") as content:
                        shutil.copyfileobj(content, stream)

                publish_file(destination, write, replace=replace)
    except OSError as error:
        raise IoFailure.from_oserror(error) from error
    else:
        return destination
