# SPDX-License-Identifier: MPL-2.0
"""Compare original ODF/PDF documents through temporary native renders when needed."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import PackageError
from odfa11y.fidelity import compare_pdfs
from odfa11y.odf import OdfDocument
from odfa11y.pdf import export_pdfua

from .native import NativeOptions, native_export_settings

if TYPE_CHECKING:
    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.report import Report

PDF_MAGIC = b"%PDF"


def is_pdf(path: Path) -> bool:
    """Sniff four bytes from a regular input with a nonblocking descriptor.

    Returns
    -------
    bool
        Whether the input has the PDF signature.

    Raises
    ------
    PackageError
        The selected or opened input is nonregular.

    """
    if not stat.S_ISREG(path.stat().st_mode):
        msg = f"Input {path} must be a regular file (ordinary file aliases are supported)"
        raise PackageError(msg)
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            msg = f"Input {path} must be a regular file"
            raise PackageError(msg)
        return os.read(descriptor, len(PDF_MAGIC)) == PDF_MAGIC
    finally:
        os.close(descriptor)


def compare_documents(
    source: str | Path,
    candidate: str | Path,
    policy: FidelityPolicy,
    diff_dir: str | Path | None = None,
    options: NativeOptions | None = None,
) -> Report:
    """Preflight both inputs, render ODF inputs privately, and compare PDF fidelity.

    Original ODF inputs retain their identity at the native boundary. Temporary
    renders and the shared LibreOffice profile survive through comparison and are
    removed before return. The returned report identifies original inputs.

    Returns
    -------
    Report
        Fidelity findings under the supplied policy, with original source identities.

    """
    options = options or NativeOptions()
    source, candidate = Path(source), Path(candidate)
    source_pdf, candidate_pdf = is_pdf(source), is_pdf(candidate)
    with tempfile.TemporaryDirectory(prefix="odfa11y-compare-") as scratch:
        work = Path(scratch)
        left = _render_input(source, work, options, pdf=source_pdf, name="source")
        right = _render_input(candidate, work, options, pdf=candidate_pdf, name="candidate")
        if options.on_progress is not None:
            options.on_progress("compare-fidelity", "running")
        report = compare_pdfs(left, right, policy, diff_dir=diff_dir)
        if options.on_progress is not None:
            options.on_progress("compare-fidelity", "completed")
    report.subject = f"{candidate.name} vs {source.name}"
    report.sources = (candidate, source)
    return report


def _render_input(path: Path, work: Path, options: NativeOptions, *, pdf: bool, name: str) -> Path:
    if pdf:
        return path
    settings = native_export_settings(
        OdfDocument.open(path), options.soffice, options.timeout, work / "profile"
    )
    if options.on_progress is not None:
        options.on_progress(f"export-{name}", "running")
    rendered = export_pdfua(path, work / f"{name}.pdf", settings)
    if options.on_progress is not None:
        options.on_progress(f"export-{name}", "passed")
    return rendered
