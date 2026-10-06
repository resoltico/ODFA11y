# SPDX-License-Identifier: MPL-2.0
"""Export Writer documents to PDF/UA through LibreOffice."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def export_pdfua(
    source_odt: str | Path,
    destination_pdf: str | Path,
    *,
    soffice: str | Path | None = None,
    timeout: int = 120,
) -> Path:
    """Export a Writer document through an isolated LibreOffice profile.

    Returns
    -------
    Path
        The exported PDF path.

    Raises
    ------
    RuntimeError
        LibreOffice fails or returns without producing a PDF.

    """
    source_odt = Path(source_odt).resolve()
    destination_pdf = Path(destination_pdf).resolve()
    destination_pdf.parent.mkdir(parents=True, exist_ok=True)

    executable = _find_soffice(soffice)
    export_options = (
        "pdf:writer_pdf_Export:{"
        '"PDFUACompliance":{"type":"boolean","value":"true"},'
        '"UseTaggedPDF":{"type":"boolean","value":"true"},'
        '"DisplayPDFDocumentTitle":{"type":"boolean","value":"true"},'
        '"ExportBookmarks":{"type":"boolean","value":"true"},'
        '"EnableTextAccessForAccessibilityTools":{"type":"boolean","value":"true"}'
        "}"
    )

    with (
        tempfile.TemporaryDirectory(prefix="odfa11y-lo-profile-") as profile_dir,
        tempfile.TemporaryDirectory(prefix="odfa11y-pdf-export-") as out_dir,
    ):
        profile_uri = Path(profile_dir).resolve().as_uri()
        cmd = [
            executable,
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            "--convert-to",
            export_options,
            "--outdir",
            out_dir,
            str(source_odt),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode != 0:
            msg = (
                "LibreOffice PDF/UA export failed.\n"
                f"command: {' '.join(cmd)}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
            raise RuntimeError(msg)
        produced = Path(out_dir) / f"{source_odt.stem}.pdf"
        if not produced.is_file():
            msg = (
                "LibreOffice returned successfully but did not create the expected PDF.\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
            raise RuntimeError(msg)
        shutil.copy2(produced, destination_pdf)
    return destination_pdf


def _find_soffice(value: str | Path | None) -> str:
    if value is not None:
        path = Path(value)
        if path.is_file():
            return str(path)
        resolved = shutil.which(str(value))
        if resolved:
            return resolved
        msg = f"LibreOffice executable not found: {value}"
        raise FileNotFoundError(msg)
    for candidate in ("soffice", "libreoffice"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    msg = "LibreOffice/soffice was not found on PATH."
    raise FileNotFoundError(msg)
