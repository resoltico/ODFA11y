# SPDX-License-Identifier: MPL-2.0
"""Writer exports establish heading behavior and the header-column capability boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.families.text import HeadingLevel, MarkTableHeaders, SetHeadingLevels, TableHeaders
from odfa11y.families.text.headings import heading_fingerprint, heading_location
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, select_elements, validate
from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

from .corpus_manifest import CORPUS
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
def test_explicit_levels_reach_real_writer_pdf_heading_roles(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = CORPUS / "headings-skipped.odt"
    headings = select_elements(OdfDocument.open(source).tree(Part.CONTENT), "//text:h")
    decisions = {
        heading_location(heading, index).path: HeadingLevel(index, heading_fingerprint(heading))
        for index, heading in enumerate(headings, 1)
    }
    baseline = export_pdfua(
        source, tmp_path / "baseline.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert "PDF012" in {f.rule_id for f in audit_pdfua(baseline).findings}
    edited = tmp_path / "headings.odt"
    remediate(source, edited, [SetHeadingLevels(decisions)])
    pdf = export_pdfua(
        edited, tmp_path / "headings.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    report = audit_pdfua(pdf)
    assert {role: report.metadata["structure_tags"].get(role) for role in ("H1", "H2", "H3")} == {
        "H1": 1,
        "H2": 1,
        "H3": 1,
    }
    assert "PDF012" not in {f.rule_id for f in report.findings}
    assert report.passed
    assert validate_pdfua(pdf, executable=verapdf).compliant


@pytest.mark.integration
def test_header_columns_preserve_source_semantics_and_do_not_hide_missing_pdf_headers(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = CORPUS / "table-no-header-row.odt"
    edited = tmp_path / "columns.odt"
    remediate(source, edited, [MarkTableHeaders({"Table1": TableHeaders(columns=1)})])
    assert validate(OdfDocument.open(edited)).count == validate(OdfDocument.open(source)).count
    assert "TXT021" not in {f.rule_id for f in audit_odf(edited).findings}
    pdf = export_pdfua(
        edited, tmp_path / "columns.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    report = audit_pdfua(pdf)
    assert report.metadata["structure_tags"].get("TH", 0) == 0
    assert "PDF015" in {f.rule_id for f in report.findings}
    # The independent validator does not detect this missing header semantics property.
    assert validate_pdfua(pdf, executable=verapdf).compliant
    clean = make_minimal_odt(tmp_path / "clean.odt", with_data_table=True)
    clean_columns = tmp_path / "clean-columns.odt"
    remediate(clean, clean_columns, [MarkTableHeaders({"Data": TableHeaders(columns=1)})])
    assert validate(OdfDocument.open(clean_columns)).count == 0
    record = run_pipeline(
        clean_columns,
        [SetMetadata(title="Header column boundary", language="en-US")],
        FidelityPolicy(),
        tmp_path / "evidence",
        PipelineOptions(profile="production", soffice=soffice, verapdf_path=verapdf),
    )
    assert record.failed_stage == "audit-pdf", [stage.as_dict() for stage in record.stages]
    assert not record.passed
