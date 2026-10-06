# SPDX-License-Identifier: MPL-2.0
"""Pdf export for ODF accessibility workflows."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from lxml import etree

from .odt_package import secure_xml_parser


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


def run_verapdf(
    pdf_path: str | Path,
    *,
    executable: str | Path | None = None,
    flavour: str = "ua1",
    timeout: int = 180,
) -> tuple[bool, str]:
    """Validate a PDF with veraPDF and return compliance and its XML report.

    Returns
    -------
    tuple[bool, str]
        Compliance across all validation reports, and the original XML output.

    Raises
    ------
    FileNotFoundError
        The validator executable cannot be found.
    RuntimeError
        The validator fails or returns an invalid XML report.

    """
    exe = str(executable) if executable is not None else shutil.which("verapdf")
    if not exe:
        msg = "veraPDF was not found on PATH. Install veraPDF or pass --verapdf /path/to/verapdf."
        raise FileNotFoundError(msg)
    cmd = [exe, "-f", flavour, "--format", "xml", "--loglevel", "0", str(Path(pdf_path).resolve())]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0 and not proc.stdout.strip():
        msg = f"veraPDF failed: {proc.stderr.strip()}"
        raise RuntimeError(msg)
    try:
        root = etree.fromstring(proc.stdout.encode("utf-8"), parser=secure_xml_parser())
    except etree.XMLSyntaxError as exc:
        msg = (
            f"Could not parse veraPDF report as XML. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        raise RuntimeError(msg) from exc
    nodes = root.xpath("//*[local-name()='validationReport']")
    if not nodes:
        msg = "veraPDF report contains no validationReport element."
        raise RuntimeError(msg)
    compliant = all(node.get("isCompliant") == "true" for node in nodes)
    return compliant, proc.stdout


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
