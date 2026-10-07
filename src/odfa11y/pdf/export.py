# SPDX-License-Identifier: MPL-2.0
"""Export ODF documents to PDF/UA through LibreOffice."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import OutputError, ToolFailedError
from odfa11y.external_tools import find_executable, identify, run_bounded
from odfa11y.staging import staging_sibling

if TYPE_CHECKING:
    from odfa11y.external_tools import ToolIdentity

EXPORT_OPTIONS: dict[str, dict[str, str]] = {
    "PDFUACompliance": {"type": "boolean", "value": "true"},
    "UseTaggedPDF": {"type": "boolean", "value": "true"},
    "DisplayPDFDocumentTitle": {"type": "boolean", "value": "true"},
    "ExportBookmarks": {"type": "boolean", "value": "true"},
    "EnableTextAccessForAccessibilityTools": {"type": "boolean", "value": "true"},
}


def find_soffice(requested: str | Path | None = None) -> str:
    """Locate the LibreOffice executable.

    Returns
    -------
    str
        The executable path.

    """
    return find_executable(requested, ("soffice", "libreoffice"))


def identify_soffice(executable: str) -> ToolIdentity:
    """Report LibreOffice's version.

    Returns
    -------
    ToolIdentity
        The name and version, or ``unknown`` when it cannot be read.

    """
    return identify("LibreOffice", executable, ("--version",))


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """How LibreOffice exports: the family's PDF filter, the tool, the time limit, the profile.

    A temporary LibreOffice profile is used unless ``profile_dir`` is given; the caller
    then owns that directory, so several exports can share one profile sequentially.
    """

    pdf_filter: str
    soffice: str | Path | None = None
    timeout: int = 120
    profile_dir: str | Path | None = None


def export_pdfua(source: str | Path, destination_pdf: str | Path, settings: ExportSettings) -> Path:
    """Export a document with the fixed PDF/UA options, publishing the PDF atomically.

    Returns
    -------
    Path
        The exported PDF path.

    Raises
    ------
    OutputError
        The destination is the source document.
    ToolFailedError
        LibreOffice fails, times out, or returns without producing a PDF.

    """
    source = Path(source).resolve()
    destination = Path(destination_pdf).resolve()
    if source == destination:
        msg = f"Destination must differ from the source: {destination.name}"
        raise OutputError(msg)
    executable = find_soffice(settings.soffice)
    destination.parent.mkdir(parents=True, exist_ok=True)
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
            raise ToolFailedError(msg) from exc
        produced = Path(out_dir) / f"{source.stem}.pdf"
        if completed.returncode != 0 or not produced.is_file():
            msg = f"LibreOffice PDF/UA export failed (exit status {completed.returncode})."
            raise ToolFailedError(
                msg, details=f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
            )
        _publish(produced, destination)
    return destination


def _publish(produced: Path, destination: Path) -> None:
    temporary = staging_sibling(destination)
    try:
        shutil.copyfile(produced, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
