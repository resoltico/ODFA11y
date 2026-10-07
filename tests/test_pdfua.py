# SPDX-License-Identifier: MPL-2.0
"""LibreOffice export against the built-in inspector and against real veraPDF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter

from odfa11y.errors import OutputError, ToolNotFoundError
from odfa11y.odf import PackageStorage
from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua

from .fixtures import make_minimal_odt

WRITER = "writer_pdf_Export"

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

RICH_BODY = (
    b'<text:h text:outline-level="1" text:style-name="Heading1">Items</text:h>'
    b'<text:list><text:list-item><text:p text:style-name="Body">First</text:p></text:list-item>'
    b'<text:list-item><text:p text:style-name="Body">Second</text:p></text:list-item></text:list>'
    b'<text:p text:style-name="Body">See <text:a xlink:type="simple" '
    b'xlink:href="https://example.test/a">the site</text:a>.</text:p>'
)


def test_export_to_the_source_path_is_refused(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(OutputError):
        export_pdfua(source, source, ExportSettings(WRITER))


def test_export_without_libreoffice_is_a_not_found_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(ToolNotFoundError):
        export_pdfua(
            source, tmp_path / "out.pdf", ExportSettings(WRITER, soffice=tmp_path / "absent")
        )


@pytest.mark.integration
def test_libreoffice_pdfua_export_has_core_markers(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "doc.odt"),
        tmp_path / "doc.pdf",
        ExportSettings(WRITER, soffice=soffice),
    )
    report = audit_pdfua(pdf)
    assert report.error_count == 0, [f.as_dict() for f in report.findings]
    assert report.metadata["pdfua_part"] == 1
    assert report.metadata["language"] == "en-GB"
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".doc.pdf")]


@pytest.mark.integration
def test_libreoffice_export_passes_real_verapdf_pdfua_validation(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    pdf = export_pdfua(
        make_minimal_odt(tmp_path / "doc.odt"),
        tmp_path / "doc.pdf",
        ExportSettings(WRITER, soffice=soffice),
    )
    result = validate_pdfua(pdf, executable=verapdf)
    assert result.compliant, result.raw_xml
    assert result.identity.version != "unknown"


@pytest.mark.integration
def test_structural_checks_agree_with_verapdf_on_a_document_with_lists_tables_and_links(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = make_minimal_odt(tmp_path / "rich.odt", with_data_table=True, with_table_header=True)
    package = PackageStorage(source)
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + RICH_BODY, 1),
    )
    rich = tmp_path / "rich-doc.odt"
    package.save(rich)
    pdf = export_pdfua(rich, tmp_path / "rich.pdf", ExportSettings(WRITER, soffice=soffice))
    report = audit_pdfua(pdf)
    assert not {f.rule_id for f in report.findings} & {
        "PDF012",
        "PDF013",
        "PDF014",
        "PDF016",
        "PDF017",
        "PDF018",
    }
    assert report.metadata["link_structure_elements"] >= 1
    result = validate_pdfua(pdf, executable=verapdf)
    failed = [f"{f.clause}-{f.test_number}: {f.description}" for f in result.failures]
    assert result.compliant, failed


@pytest.mark.integration
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
    pdf = export_pdfua(wrapped, tmp_path / "wrapped.pdf", ExportSettings(WRITER, soffice=soffice))
    report = audit_pdfua(pdf)
    assert report.metadata["link_annotations"] >= 2  # one annotation per wrapped line
    assert not {f.rule_id for f in report.findings} & {"PDF016", "PDF017", "PDF018"}


@pytest.mark.integration
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
