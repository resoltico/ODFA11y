# SPDX-License-Identifier: MPL-2.0
"""Export ODF documents to PDF/UA through LibreOffice."""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from odfa11y.errors import OutputOccupied, Remedy, RemedyAction, ToolFailure, ToolUnavailable
from odfa11y.native.process import find_executable, identify_running_or_by_file, run_bounded
from odfa11y.native.tools import LibreOffice
from odfa11y.publish import publish_file
from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout

MINIMUM_LIBREOFFICE_VERSION = (26, 8)

EXPORT_OPTIONS: dict[str, dict[str, str]] = {
    "PDFUACompliance": {"type": "boolean", "value": "true"},
    "UseTaggedPDF": {"type": "boolean", "value": "true"},
    "DisplayPDFDocumentTitle": {"type": "boolean", "value": "true"},
    "ExportBookmarks": {"type": "boolean", "value": "true"},
    "EnableTextAccessForAccessibilityTools": {"type": "boolean", "value": "true"},
}


def find_soffice(requested: str | Path | None = None) -> str:
    """Locate LibreOffice; preparation identifies and checks the selected executable.

    Returns
    -------
    str
        The executable path.

    Raises
    ------
    ToolUnavailable
        LibreOffice is too old or its version cannot be determined.

    """
    return find_executable(requested, ("soffice", "libreoffice"))


def require_supported_version(identity: ToolIdentity) -> None:
    """Refuse LibreOffice versions below the supported minimum."""
    version = identity.version
    minimum = ".".join(str(part) for part in MINIMUM_LIBREOFFICE_VERSION)
    if (
        version == "unknown"
        or tuple(int(part) for part in version.split(".")) < MINIMUM_LIBREOFFICE_VERSION
    ):
        msg = f"LibreOffice {version} is unsupported; install LibreOffice {minimum} or newer."
        raise ToolUnavailable(msg, remedy=Remedy(RemedyAction.INSTALL_TOOL, "LibreOffice"))


def identify_soffice(executable: str, *, timeout: float = Timeout.DEFAULT) -> ToolIdentity:
    """Report LibreOffice's version.

    ``soffice --version`` never returns on Windows, so there the file's product version is read.

    Returns
    -------
    ToolIdentity
        The name and version, or ``unknown`` when it cannot be read.

    """
    return identify_running_or_by_file("LibreOffice", executable, ("--version",), timeout=timeout)


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """How LibreOffice exports: the family's PDF filter, the tool, the time limit, the profile.

    A temporary LibreOffice profile is used unless ``profile_dir`` is given; the caller
    then owns that directory, so several exports can share one profile sequentially.
    """

    pdf_filter: str
    office: LibreOffice
    timeout: int | float = Timeout.DEFAULT
    profile_dir: str | Path | None = None

    def __post_init__(self) -> None:
        """Reject an invalid duration before native work or output creation."""
        object.__setattr__(self, "timeout", Timeout(self.timeout))


def export_pdfua(source: str | Path, destination_pdf: str | Path, settings: ExportSettings) -> Path:
    """Export a document with the fixed PDF/UA options, publishing the PDF atomically.

    This is the raw application boundary and does not perform ODF resource preflight.
    Guarded ``export_document``/``compare_documents`` and the pipeline own that policy;
    direct raw-boundary library callers
    must establish their resource contract and isolate native processing themselves.

    Returns
    -------
    Path
        The exported PDF path.

    Raises
    ------
    OutputOccupied
        The destination is the source document.
    ToolFailure
        LibreOffice fails, times out, or returns without producing a PDF.

    """
    Timeout(settings.timeout)
    source = Path(source).resolve()
    destination = Path(destination_pdf).absolute()
    if source == destination.resolve():
        msg = f"Destination must differ from the source: {destination.name}"
        raise OutputOccupied(msg)
    executable = settings.office.executable
    options = f"pdf:{settings.pdf_filter}:" + json.dumps(EXPORT_OPTIONS, separators=(",", ":"))
    with (
        tempfile.TemporaryDirectory(prefix="odfa11y-lo-profile-") as temporary_profile,
        tempfile.TemporaryDirectory(prefix="odfa11y-pdf-export-") as out_dir,
    ):
        profile = (
            Path(settings.profile_dir)
            if settings.profile_dir is not None
            else Path(temporary_profile)
        )
        command = [
            executable,
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            "--convert-to",
            options,
            "--outdir",
            out_dir,
            str(source),
        ]
        try:
            completed = run_bounded(command, timeout=settings.timeout)
        except subprocess.TimeoutExpired as exc:
            msg = f"LibreOffice PDF/UA export timed out after {settings.timeout} s"
            raise ToolFailure(msg) from exc
        produced = Path(out_dir) / f"{source.stem}.pdf"
        if completed.returncode != 0 or not produced.is_file():
            msg = f"LibreOffice PDF/UA export failed (exit status {completed.returncode})."
            raise ToolFailure(
                msg, details=f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
            )
        _publish(produced, destination)
    return destination


def _publish(produced: Path, destination: Path) -> None:
    def write(stream: BinaryIO) -> None:
        with produced.open("rb") as source:
            shutil.copyfileobj(source, stream)

    publish_file(destination, write, replace=True)
