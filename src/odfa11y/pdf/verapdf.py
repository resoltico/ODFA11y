# SPDX-License-Identifier: MPL-2.0
"""Run veraPDF and read its machine-validation report."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from lxml import etree

from odfa11y.safe_xml import secure_xml_parser


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
    nodes = [node for node in root.iter("*") if etree.QName(node).localname == "validationReport"]
    if not nodes:
        msg = "veraPDF report contains no validationReport element."
        raise RuntimeError(msg)
    compliant = all(node.get("isCompliant") == "true" for node in nodes)
    return compliant, proc.stdout
