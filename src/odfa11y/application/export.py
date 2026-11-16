# SPDX-License-Identifier: MPL-2.0
"""Capture an original document and explicitly publish its guarded native export."""

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from odfa11y.application.io_errors import translate_io
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit.export import native_export_settings
from odfa11y.capture import capture_source
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.errors import IoFailure
from odfa11y.odf import OdfDocument
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.publish import publish_file, require_distinct, require_file_destination
from odfa11y.status import ExitStatus


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


@dataclass(frozen=True, slots=True)
class ExportResult:
    """The published PDF path and effective export status."""

    schema_version: Literal[1] = field(default=1, init=False)

    _output: Path

    @property
    def output(self) -> Path:
        """Return the published path for a subsequent application operation."""
        return self._output

    @JsonProperty
    def output_name(self) -> str:
        """Return the published filename without exposing its parent directories."""
        return self._output.name

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Return the completed export's effective status."""
        return ExitStatus.PASSED

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@translate_io
def export(
    source: str | Path,
    destination: str | Path,
    *,
    tools: Tools | None = None,
    replace: bool = False,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> ExportResult:
    """Publish a guarded native export with caller-selected tools."""
    return ExportResult(
        export_document(
            source,
            destination,
            tools or Tools(),
            replace=replace,
            on_progress=observer,
            native_tools=native_tools,
        )
    )
