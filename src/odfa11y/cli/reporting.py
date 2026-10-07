# SPDX-License-Identifier: MPL-2.0
"""Cli reporting for ODF accessibility workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pypdf
from lxml import etree

from odfa11y import __version__
from odfa11y.odf import OdtPackage, StyleCatalog
from odfa11y.pdf import run_verapdf
from odfa11y.report import Severity, max_severity_exit_code, render_report

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import AuditReport


def style_report(source: Path, output_format: str) -> int:
    """Print paragraph-style usage for a document.

    Returns
    -------
    int
        Zero after the report is printed.

    """
    package = OdtPackage(source)
    catalog = StyleCatalog(package)
    rows = catalog.paragraph_usage()
    if output_format == "json":
        print(
            json.dumps(
                [
                    {
                        "style": row.style_name,
                        "count": row.count,
                        "parent": row.parent,
                        "spacing": row.spacing,
                    }
                    for row in rows
                ],
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"Paragraph styles in {source}:")
        for row in rows:
            print(
                f"- {row.style_name}: {row.count} use(s); "
                f"parent={row.parent!r}; spacing={row.spacing}"
            )
    return 0


def append_verapdf_result(report: AuditReport, pdf: Path, value: str | None) -> None:
    """Add the veraPDF validation outcome to a PDF report when requested."""
    if not value:
        return
    executable = None if value == "auto" else value
    try:
        compliant, _raw = run_verapdf(pdf, executable=executable, flavour="ua1")
    except FileNotFoundError as exc:
        report.add("VERA000", Severity.WARNING, str(exc), location=str(pdf))
        return
    if compliant:
        report.metadata["veraPDF_PDF_UA_1"] = "compliant"
    else:
        report.add(
            "VERA001",
            Severity.ERROR,
            "veraPDF reports that the PDF is not compliant with the PDF/UA-1 profile.",
            location=str(pdf),
        )
        report.metadata["veraPDF_PDF_UA_1"] = "non-compliant"


def print_multi_reports(reports: list[AuditReport], output_format: str, *, strict: bool) -> int:
    """Print several reports in one format and combine their exit status.

    Returns
    -------
    int
        The highest exit code across the reports.

    """
    if output_format == "json":
        print(
            json.dumps([r.as_dict() for r in reports], indent=2, ensure_ascii=False, sort_keys=True)
        )
    else:
        print("\n\n".join(render_report(r) for r in reports))
    return max(max_severity_exit_code(r, strict=strict) for r in reports)


def doctor(output_format: str) -> int:
    """Print tool and dependency versions used by this installation.

    Returns
    -------
    int
        Zero after the versions are printed.

    """
    info = {
        "odfa11y": __version__,
        "python": sys.version.split()[0],
        "lxml": etree.__version__,
        "pypdf": pypdf.__version__,
        "soffice": shutil.which("soffice") or shutil.which("libreoffice"),
        "veraPDF": shutil.which("verapdf"),
    }
    if info["soffice"]:
        try:
            proc = subprocess.run(
                [info["soffice"], "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            info["LibreOffice_version"] = (proc.stdout or proc.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            info["LibreOffice_version_error"] = str(exc)
    if output_format == "json":
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {value or 'not found'}")
    return 0
