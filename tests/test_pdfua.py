# SPDX-License-Identifier: MPL-2.0
"""Test pdfua for ODF accessibility workflows."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from odfa11y.pdfua import audit_pdfua, export_pdfua

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
def test_libreoffice_pdfua_export_has_core_markers(tmp_path: Path) -> None:
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        pytest.skip("LibreOffice not installed")
    source = make_minimal_odt(tmp_path / "source.odt")
    pdf = tmp_path / "source.pdf"
    export_pdfua(source, pdf)
    report = audit_pdfua(pdf)
    assert report.error_count == 0, [issue.as_dict() for issue in report.issues]
    assert report.metadata["pdfua_part"] == 1
    assert report.metadata["language"] == "en-GB"
