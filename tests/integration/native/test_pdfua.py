# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for pdfua."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from pypdf import PdfWriter

from odfa11y.native.libreoffice import export_pdfua
from odfa11y.odf import PackageStorage
from odfa11y.pdf import audit_pdfua
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.pdf.structure.links import PdfLinkMeasurements
from odfa11y.pdf.structure.marked_content import MarkedContentMeasurements
from odfa11y.rules import registry as rules
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native import export_settings, validate_pdfua
from tests.fixtures.writer import make_minimal_odt
from tests.native.test_pdfua import LINK_DESCRIPTION_RULES, RICH_BODY, WRITER


def test_libreoffice_pdfua_export_has_core_markers(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "doc.odt"),
        tmp_path / "doc.pdf",
        export_settings(WRITER, soffice=soffice),
    )
    report = audit_pdfua(pdf)
    assert report.error_count == 0, [f.as_dict() for f in report.findings]
    assert measured(measurement(report, PdfMeasurements).ua_part) == 1
    assert measured(measurement(report, PdfMeasurements).language) == "en-GB"
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".doc.pdf")]


def test_libreoffice_export_content_is_fully_tagged(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(
        tmp_path / "rich.odt", features={"with_data_table": True, "with_table_header": True}
    )
    package = PackageStorage(source)
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + RICH_BODY, 1),
    )
    rich = package.save(tmp_path / "rich-doc.odt")
    pdf = export_pdfua(rich, tmp_path / "rich.pdf", export_settings(WRITER, soffice=soffice))
    report = audit_pdfua(pdf)
    assert not {f.rule_id for f in report.findings} & {
        rules.PDF021.id,
        rules.PDF022.id,
        rules.PDF023.id,
        rules.PDF024.id,
    }
    assert measured(measurement(report, MarkedContentMeasurements).marked_content_id_count) >= 1


@pytest.mark.usefixtures("required_verapdf")
def test_libreoffice_export_passes_real_verapdf_pdfua_validation(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "doc.odt"),
        tmp_path / "doc.pdf",
        export_settings(WRITER, soffice=soffice),
    )
    result = validate_pdfua(pdf, executable=verapdf)
    assert result.compliant, result.raw_xml
    assert result.identity.version != "unknown"


@pytest.mark.usefixtures("required_verapdf")
def test_structural_checks_agree_with_verapdf_on_a_document_with_lists_tables_and_links(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = make_minimal_odt(
        tmp_path / "rich.odt", features={"with_data_table": True, "with_table_header": True}
    )
    package = PackageStorage(source)
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + RICH_BODY, 1),
    )
    rich = tmp_path / "rich-doc.odt"
    package.save(rich)
    pdf = export_pdfua(rich, tmp_path / "rich.pdf", export_settings(WRITER, soffice=soffice))
    report = audit_pdfua(pdf)
    assert not {f.rule_id for f in report.findings} & {
        rules.PDF013.id,
        rules.PDF014.id,
        rules.PDF015.id,
        rules.PDF017.id,
        rules.PDF018.id,
        rules.PDF019.id,
    }
    assert measured(measurement(report, PdfLinkMeasurements).link_structure_element_count) >= 1
    result = validate_pdfua(pdf, executable=verapdf)
    failed = {(f.clause, f.test_number) for f in result.failures}
    assert rules.PDF020.id in {f.rule_id for f in report.findings}
    assert failed == LINK_DESCRIPTION_RULES, failed


def test_a_hyperlink_wrapped_over_several_lines_is_one_correct_link(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    words = " ".join(f"word{index}" for index in range(120))
    body = (
        b'<text:p text:style-name="Body">Read <text:a xlink:type="simple" '
        b'xlink:href="https://example.test/long">' + words.encode() + b"</text:a> now.</text:p>"
    )
    package = PackageStorage(make_minimal_odt(tmp_path / "wrap.odt"))
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + body, 1),
    )
    wrapped = package.save(tmp_path / "wrapped.odt")
    pdf = export_pdfua(wrapped, tmp_path / "wrapped.pdf", export_settings(WRITER, soffice=soffice))
    report = audit_pdfua(pdf)
    assert (
        measured(measurement(report, PdfLinkMeasurements).link_annotation_count) >= 2
    )  # one annotation per wrapped line
    assert not {f.rule_id for f in report.findings} & {
        rules.PDF017.id,
        rules.PDF018.id,
        rules.PDF019.id,
    }


@pytest.mark.usefixtures("required_verapdf")
def test_real_verapdf_reports_the_failed_rules_of_an_untagged_pdf(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    verapdf = external_tool("verapdf")
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / "untagged.pdf"
    writer.write(pdf)
    result = validate_pdfua(pdf, executable=verapdf)
    assert not result.compliant
    assert {(f.clause, f.test_number) for f in result.failures} >= {("6.2", "1"), ("7.1", "11")}
    assert all(f.specification.startswith("ISO 14289-1") for f in result.failures)
    assert all(f.description for f in result.failures)
