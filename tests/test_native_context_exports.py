# SPDX-License-Identifier: MPL-2.0
"""Native asset positives, document-base parity and deliberate filename limitations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.evidence import check_bundle
from odfa11y.native.export import ExportSettings, export_pdfua
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.pdf.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.pdf.fidelity.snapshot import read_snapshot
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.pipeline.profiles import profile_named
from odfa11y.remediation import SetMetadata
from odfa11y.tools import Tools

from .fixtures import make_minimal_odt
from .native_resource_fixtures import PIXELS, author_package, decoded_images, writer_resource
from .operation_execution import execute_operations
from .reviewed_plans import reviewed_plan

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("layout", ["flat", "native-package", "alias", "navigation-base"])
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
        source, tmp_path / "direct.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert ((4, 4), PIXELS) in decoded_images(direct)
    baseline = read_snapshot(direct)
    assert baseline.links
    output = tmp_path / "evidence"
    result = execute(
        source,
        reviewed_plan(source, [SetMetadata(language="en-GB")], FidelityPolicy()),
        output,
        RunSettings(
            tools=Tools(soffice=soffice, verapdf=verapdf), profile=profile_named("production")
        ),
    )
    assert result.passed, result.as_dict()
    for name in ["source.pdf", "remediated.pdf"]:
        pdf = output / name
        assert ((4, 4), PIXELS) in decoded_images(pdf)
        actual = read_snapshot(pdf)
        assert actual.links == baseline.links
        assert actual.text == baseline.text
        assert compare_pdfs(direct, pdf, FidelityPolicy()).passed
    published = output / ("remediated" + source.suffix)
    expected = tmp_path / ("expected" + source.suffix)
    execute_operations(source, expected, [SetMetadata(language="en-GB")])
    assert published.read_bytes() == expected.read_bytes()
    assert source.read_bytes() == original
    assert not execute_operations(
        published, tmp_path / ("again" + source.suffix), [SetMetadata(language="en-GB")]
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
        source, tmp_path / "original.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert "story.odt" in read_snapshot(direct).text
    assert ".odfa11y-source-" not in read_snapshot(direct).text
    output = tmp_path / "evidence"
    for repeat in [1, 2]:
        result = execute(
            source,
            reviewed_plan(source, [], FidelityPolicy()),
            output / str(repeat),
            RunSettings(tools=Tools(soffice=soffice), profile=profile_named("verify")),
        )
        assert result.failed_stage == "export-source"
        assert result.exit_status == 3
        assert not (output / str(repeat) / "source.pdf").exists()
        assert check_bundle(output / str(repeat)) == []
    inspected = tmp_path / "inspected"
    assert execute(
        source,
        reviewed_plan(source, [], FidelityPolicy()),
        inspected,
        RunSettings(profile=profile_named("source")),
    ).passed
    published = inspected / "remediated.odt"
    assert published.read_bytes() == original
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".odfa11y-source-*"))
    # A deliberate destination filename is real visible change; fidelity still rejects it.
    renamed_pdf = export_pdfua(
        published, tmp_path / "candidate.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert "remediated.odt" in read_snapshot(renamed_pdf).text
    assert not compare_pdfs(direct, renamed_pdf, FidelityPolicy()).passed


def _set_navigation_base(source: Path) -> None:
    document = OdfDocument.open(source)
    link = document.tree(Part.CONTENT).find(".//text:a", NS)
    assert link is not None
    link.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/docs/")
    document.save(source)
