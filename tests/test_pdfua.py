# SPDX-License-Identifier: MPL-2.0
"""Check LibreOffice PDF/UA export against the project's inspector and real veraPDF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter

from odfa11y.pdf import audit_pdfua, export_pdfua, run_verapdf

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
def test_libreoffice_pdfua_export_has_core_markers(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "source.odt"), tmp_path / "source.pdf", soffice=soffice
    )
    report = audit_pdfua(pdf)
    assert report.error_count == 0, [issue.as_dict() for issue in report.issues]
    assert report.metadata["pdfua_part"] == 1
    assert report.metadata["language"] == "en-GB"


@pytest.mark.integration
def test_libreoffice_export_passes_real_verapdf_pdfua_validation(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "source.odt"), tmp_path / "source.pdf", soffice=soffice
    )
    compliant, report = run_verapdf(pdf, executable=verapdf)
    assert compliant, report


@pytest.mark.integration
def test_real_verapdf_rejects_an_untagged_pdf(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    verapdf = external_tool("verapdf")
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / "untagged.pdf"
    writer.write(pdf)
    compliant, report = run_verapdf(pdf, executable=verapdf)
    assert not compliant
    assert "validationReport" in report
