# SPDX-License-Identifier: MPL-2.0
"""Cli reporting for ODF accessibility workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import lxml
import pypdf

from . import __version__
from .models import Severity
from .odt_package import OdtPackage
from .pdfua import run_verapdf
from .reporting import max_severity_exit_code, render_report
from .styles import StyleCatalog

if TYPE_CHECKING:
    from pathlib import Path

    from .models import AuditReport


def _style_report(source: Path, output_format: str) -> int:
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


def _append_verapdf_result(report: AuditReport, pdf: Path, value: str | None) -> None:
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


def _print_multi_reports(reports: list[AuditReport], output_format: str, *, strict: bool) -> int:
    if output_format == "json":
        print(
            json.dumps([r.as_dict() for r in reports], indent=2, ensure_ascii=False, sort_keys=True)
        )
    else:
        print("\n\n".join(render_report(r) for r in reports))
    return max(max_severity_exit_code(r, strict=strict) for r in reports)


def _doctor(output_format: str) -> int:
    info = {
        "odfa11y": __version__,
        "python": sys.version.split()[0],
        "lxml": lxml.__version__,
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
