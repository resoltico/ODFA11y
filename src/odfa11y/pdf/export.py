# SPDX-License-Identifier: MPL-2.0
"""Export Writer documents to PDF/UA through LibreOffice."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import OutputError, ToolFailedError
from odfa11y.external_tools import find_executable, identify
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


def export_pdfua(
    source_odt: str | Path,
    destination_pdf: str | Path,
    *,
    soffice: str | Path | None = None,
    timeout: int = 120,
    profile_dir: str | Path | None = None,
) -> Path:
    """Export a Writer document with the fixed PDF/UA options, publishing the PDF atomically.

    A temporary LibreOffice profile is used unless ``profile_dir`` is given; the caller
    then owns that directory, so several exports can share one profile sequentially.

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
    source = Path(source_odt).resolve()
    destination = Path(destination_pdf).resolve()
    if source == destination:
        msg = f"Destination must differ from the source: {destination}"
        raise OutputError(msg)
    executable = find_soffice(soffice)
    destination.parent.mkdir(parents=True, exist_ok=True)
    options = "pdf:writer_pdf_Export:" + json.dumps(EXPORT_OPTIONS, separators=(",", ":"))
    with (
        tempfile.TemporaryDirectory(prefix="odfa11y-lo-profile-") as temporary_profile,
        tempfile.TemporaryDirectory(prefix="odfa11y-pdf-export-") as out_dir,
    ):
        profile = Path(profile_dir) if profile_dir is not None else Path(temporary_profile)
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
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            msg = f"LibreOffice PDF/UA export timed out after {timeout} s"
            raise ToolFailedError(msg) from exc
        produced = Path(out_dir) / f"{source.stem}.pdf"
        if completed.returncode != 0 or not produced.is_file():
            msg = (
                "LibreOffice PDF/UA export failed.\n"
                f"command: {' '.join(command)}\n"
                f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
            )
            raise ToolFailedError(msg)
        _publish(produced, destination)
    return destination


def _publish(produced: Path, destination: Path) -> None:
    temporary = staging_sibling(destination)
    try:
        shutil.copyfile(produced, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
