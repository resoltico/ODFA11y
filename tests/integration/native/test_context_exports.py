# SPDX-License-Identifier: MPL-2.0
"""Native asset positives, document-base parity and deliberate filename limitations."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.application.export import export_document
from odfa11y.application.tools import Tools
from odfa11y.errors import DocumentRefusal, RemedyAction
from odfa11y.evidence import check_bundle
from odfa11y.native.libreoffice import ExportSettings, export_pdfua
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.pdf.fidelity.snapshot import read_snapshot
from odfa11y.plans.fidelity import Pagination
from odfa11y.status import Profile
from tests.fixtures.answers import metadata_input
from tests.fixtures.native import export_settings
from tests.fixtures.native_resources import PIXELS, author_package, decoded_images, writer_resource
from tests.fixtures.operations import apply_answers
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import RunSettings, execute
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("layout", ["flat", "native-package", "alias", "navigation-base"])
@pytest.mark.usefixtures("required_verapdf")
def test_supported_context_retains_real_pixels_text_and_relative_navigation(
    tmp_path: Path, external_tool: Callable[..., str], layout: str
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    flat = writer_resource(tmp_path)
    source = (
        flat
        if layout in {"flat", "navigation-base"}
        else author_package(flat, soffice, tmp_path / "authored")
    )
    if layout == "navigation-base":
        _set_navigation_base(source)
    if layout == "alias":
        alias = tmp_path / "alias.odt"
        alias.symlink_to(source)
        source = alias
    original = source.read_bytes()
    direct = export_pdfua(
        source, tmp_path / "direct.pdf", export_settings("writer_pdf_Export", soffice)
    )
    assert ((4, 4), PIXELS) in decoded_images(direct)
    baseline = read_snapshot(direct)
    assert baseline.links
    output = tmp_path / "evidence"
    result = execute(
        source,
        reviewed_plan(source, [metadata_input(language="en-GB")], Pagination.SAME()),
        output,
        RunSettings(
            tools=Tools(soffice=soffice, verapdf=verapdf), profile=Profile.parse("production")
        ),
    )
    assert result.passed, result.as_dict()
    for name in ["source.pdf", "remediated.pdf"]:
        pdf = output / name
        assert ((4, 4), PIXELS) in decoded_images(pdf)
        actual = read_snapshot(pdf)
        assert actual.links == baseline.links
        assert actual.text == baseline.text
        assert compare_pdfs(direct, pdf, Pagination.SAME()).report.error_count == 0
    published = output / ("remediated" + source.suffix)
    expected = tmp_path / ("expected" + source.suffix)
    apply_answers(source, expected, [metadata_input(language="en-GB")])
    assert published.read_bytes() == expected.read_bytes()
    assert source.read_bytes() == original
    assert not apply_answers(
        published, tmp_path / ("again" + source.suffix), [metadata_input(language="en-GB")]
    ).changed
    assert not list(source.resolve().parent.glob(".odfa11y-source-*"))
    assert check_bundle(output) == []


@pytest.mark.parametrize("display", ["name-and-extension", "full"])
def test_native_filename_context_is_refused_without_freezing_fields(
    tmp_path: Path, external_tool: Callable[..., str], display: str
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(tmp_path / "story.odt")
    document = OdfDocument.open(source)
    paragraph = document.tree(Part.CONTENT).find(".//text:p", NS)
    assert paragraph is not None
    paragraph.text = "Filename: "
    field = etree.SubElement(paragraph, qn("text", "file-name"))
    field.set(qn("text", "display"), display)
    field.text = "Authored cached field"
    document.save(source)
    original = source.read_bytes()
    direct = export_pdfua(
        source, tmp_path / "original.pdf", export_settings("writer_pdf_Export", soffice)
    )
    assert "story.odt" in read_snapshot(direct).text
    assert ".odfa11y-source-" not in read_snapshot(direct).text
    output = tmp_path / "evidence"
    for repeat in [1, 2]:
        result = execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            output / str(repeat),
            RunSettings(tools=Tools(soffice=soffice), profile=Profile.PDF),
        )
        assert result.failed_stage == "export-source"
        assert result.exit_status == 2
        assert not (output / str(repeat) / "source.pdf").exists()
        assert check_bundle(output / str(repeat)) == []
    inspected = tmp_path / "inspected"
    assert execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        inspected,
        RunSettings(profile=Profile.parse("source")),
    ).passed
    published = inspected / "remediated.odt"
    assert published.read_bytes() == original
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".odfa11y-source-*"))
    # A deliberate destination filename is real visible change; fidelity still rejects it.
    renamed_pdf = export_pdfua(
        published, tmp_path / "candidate.pdf", export_settings("writer_pdf_Export", soffice)
    )
    assert "remediated.odt" in read_snapshot(renamed_pdf).text
    assert compare_pdfs(direct, renamed_pdf, Pagination.SAME()).report.error_count != 0


def _set_navigation_base(source: Path) -> None:
    document = OdfDocument.open(source)
    link = document.tree(Part.CONTENT).find(".//text:a", NS)
    assert link is not None
    link.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/docs/")
    document.save(source)


@pytest.mark.parametrize("xml_base", [False, True])
def test_private_capture_refuses_location_dependent_navigation_before_native_export(
    tmp_path: Path,
    external_tool: Callable[..., str],
    *,
    xml_base: bool,
) -> None:
    source = writer_resource(tmp_path, navigation="assets/nested/guide.html")
    if xml_base:
        _set_navigation_base(source)
    original = source.read_bytes()
    tools = Tools(soffice=external_tool("soffice", "libreoffice"))
    office = tools.resolve(libreoffice=True).libreoffice
    assert office is not None
    direct = export_pdfua(
        source, tmp_path / "direct.pdf", ExportSettings("writer_pdf_Export", office)
    )
    assert any(uri.startswith("file:") for uri, count in read_snapshot(direct).links)
    with pytest.raises(DocumentRefusal, match="relative destination") as failure:
        export_document(source, tmp_path / "captured.pdf", tools)
    assert failure.value.exit_status == 2
    assert failure.value.remedy is not None
    assert failure.value.remedy.action is RemedyAction.EDIT_IN_APPLICATION
    assert not (tmp_path / "captured.pdf").exists()
    result = execute(source, reviewed_plan(source), tmp_path / "evidence", RunSettings(tools=tools))
    assert result.exit_status == 2
    assert not (tmp_path / "evidence" / "source.pdf").exists()
    assert not (tmp_path / "evidence" / "remediated.pdf").exists()
    assert check_bundle(tmp_path / "evidence") == []
    assert source.read_bytes() == original
