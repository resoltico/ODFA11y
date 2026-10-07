# SPDX-License-Identifier: MPL-2.0
"""Only described Figures tied to executed graphic content satisfy the content gate."""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

import pytest
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
    NumberObject,
    StreamObject,
)

from odfa11y.pdf import audit_pdfua
from odfa11y.pdf.content_scan import scan_content

from .pdf_fixtures import set_page_content, tagged_writer

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report

DRAW = "0 0 m 10 10 l S"


def _audit(
    tmp_path: Path, operators: str, *, alternative: str | None = "A diagonal line"
) -> Report:
    writer = tagged_writer(["Figure"], figure_alt=alternative)
    set_page_content(writer, writer.pages[0], operators)
    path = tmp_path / "figure.pdf"
    writer.write(path)
    return audit_pdfua(path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "S",
        "0 0 m S",
        "0 0 10 10 re W n",
        "/Artifact BMC 0 0 10 10 re f EMC",
        "/Absent Do",
        "re S",
        "(words) re S",
        "[0 0 10 10] re S",
    ],
)
def test_empty_unpainted_artifact_invalid_resource_and_malformed_path_do_not_count(
    tmp_path: Path, content: str
) -> None:
    report = _audit(tmp_path, f"/Figure <</MCID 0>> BDC {content} EMC")
    assert "PDF010" in {finding.rule_id for finding in report.findings}
    assert report.metadata["described_graphics"] == 0


def test_painted_vector_with_a_reconciled_alternative_counts(tmp_path: Path) -> None:
    report = _audit(tmp_path, f"/Figure <</MCID 0>> BDC {DRAW} EMC")
    assert report.error_count == 0
    assert report.metadata["extractable_text_characters"] == 0
    assert report.metadata["described_graphics"] == 1


@pytest.mark.parametrize("alternative", [None, "", "   "])
def test_graphical_content_without_an_alternative_keeps_both_errors(
    tmp_path: Path, alternative: str | None
) -> None:
    report = _audit(tmp_path, f"/Figure <</MCID 0>> BDC {DRAW} EMC", alternative=alternative)
    assert {"PDF007", "PDF010"} <= {finding.rule_id for finding in report.findings}


def test_drawing_outside_the_figure_sequence_does_not_count(tmp_path: Path) -> None:
    report = _audit(tmp_path, f"/Figure <</MCID 0>> BDC EMC {DRAW}")
    assert report.metadata["described_graphics"] == 0
    assert "PDF010" in {finding.rule_id for finding in report.findings}


def test_graphics_on_another_page_with_the_same_mcid_do_not_count(tmp_path: Path) -> None:
    writer = tagged_writer(["Figure"], figure_alt="A line")
    set_page_content(writer, writer.pages[0], "/Figure <</MCID 0>> BDC EMC")
    other = writer.add_blank_page(width=100, height=100)
    set_page_content(writer, other, f"/Figure <</MCID 0>> BDC {DRAW} EMC")
    path = tmp_path / "wrong-page.pdf"
    writer.write(path)
    report = audit_pdfua(path)
    assert report.metadata["described_graphics"] == 0
    assert "PDF010" in {finding.rule_id for finding in report.findings}


def test_an_unreachable_described_figure_does_not_count(tmp_path: Path) -> None:
    writer = tagged_writer(["Figure"], figure_alt="A line")
    root = writer.root_object["/StructTreeRoot"].get_object()
    assert isinstance(root, DictionaryObject)
    root[NameObject("/K")] = ArrayObject()
    set_page_content(writer, writer.pages[0], f"/Figure <</MCID 0>> BDC {DRAW} EMC")
    path = tmp_path / "orphan.pdf"
    writer.write(path)
    report = audit_pdfua(path)
    assert report.metadata["described_graphics"] == 0
    assert "PDF010" in {finding.rule_id for finding in report.findings}


def test_child_content_references_can_supply_the_figures_graphic_content(tmp_path: Path) -> None:
    writer = tagged_writer([("Figure", ["Span"])], figure_alt="A line")
    set_page_content(writer, writer.pages[0], f"/Span <</MCID 0>> BDC {DRAW} EMC")
    path = tmp_path / "child.pdf"
    writer.write(path)
    report = audit_pdfua(path)
    assert report.metadata["described_graphics"] == 1
    assert "PDF010" not in {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize("invoked", [False, True])
@pytest.mark.parametrize("payload", [b"", b"\x00", b"\xff"])
def test_image_resources_count_only_when_invoked_in_matching_content(
    tmp_path: Path, payload: bytes, *, invoked: bool
) -> None:
    image = DecodedStreamObject()
    image.set_data(payload)
    report = _image_report(tmp_path, image, invoked=invoked)
    expected = invoked and bool(payload)
    assert report.metadata["described_graphics"] == int(expected)
    assert ("PDF010" in {finding.rule_id for finding in report.findings}) is (not expected)


def _image_report(tmp_path: Path, image: StreamObject, *, invoked: bool = True) -> Report:
    writer = tagged_writer(["Figure"], figure_alt="An image pixel")
    set_page_content(
        writer,
        writer.pages[0],
        "/Figure <</MCID 0>> BDC " + ("/Image Do" if invoked else "") + " EMC",
    )
    image.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Image"),
        NameObject("/Width"): NumberObject(1),
        NameObject("/Height"): NumberObject(1),
        NameObject("/BitsPerComponent"): NumberObject(8),
        NameObject("/ColorSpace"): NameObject("/DeviceGray"),
    })
    resources = writer.pages[0]["/Resources"].get_object()
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Image"): image})
    path = tmp_path / "image.pdf"
    writer.write(path)
    return audit_pdfua(path)


@pytest.mark.parametrize("payload", [b"", b"\x00", b"\xff"])
def test_encoded_image_presence_never_invokes_a_decompressor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    image = EncodedStreamObject()
    image[NameObject("/Filter")] = NameObject("/FlateDecode")
    StreamObject.set_data(image, zlib.compress(payload))

    def refuse_decompression(_self: EncodedStreamObject) -> bytes:
        pytest.fail("Image presence must not decode filtered image streams")

    monkeypatch.setattr(EncodedStreamObject, "get_data", refuse_decompression)
    report = _image_report(tmp_path, image)
    assert report.metadata["described_graphics"] == 1
    assert "PDF010" not in {finding.rule_id for finding in report.findings}


def test_empty_encoded_image_stream_cannot_supply_graphical_presence(tmp_path: Path) -> None:
    image = EncodedStreamObject()
    image[NameObject("/Filter")] = NameObject("/FlateDecode")
    StreamObject.set_data(image, b"")
    image[NameObject("/Length")] = NumberObject(999)
    report = _image_report(tmp_path, image)
    assert report.metadata["described_graphics"] == 0
    assert "PDF010" in {finding.rule_id for finding in report.findings}


def test_nested_artifacts_cannot_supply_graphics_to_outer_content() -> None:
    data = b"/Figure <</MCID 0>> BDC /Artifact BMC /Span <</MCID 1>> BDC 0 0 2 2 re f EMC EMC EMC"
    result = scan_content(data, lambda _: None)
    assert result.mcids == {0, 1}
    assert result.graphical_mcids == set()


def test_graphics_propagate_through_each_scope_once() -> None:
    data = b"/Figure <</MCID 0>> BDC /Span <</MCID 1>> BDC 0 0 2 2 re f EMC EMC"
    result = scan_content(data, lambda _: None)
    assert result.graphical_mcids == {0, 1}
