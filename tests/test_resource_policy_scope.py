# SPDX-License-Identifier: MPL-2.0
"""Navigation, chart context and metadata have distinct native resource semantics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.content import native_export_limitations, require_native_context
from odfa11y.errors import ToolFailedError
from odfa11y.odf import OdfDocument, Part, qn, validate

from .documents import Variant, make_package
from .resource_declaration_fixtures import declaration

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("kind", ["form-button", "form-image"])
def test_form_operation_navigation_is_not_the_graphical_resource(tmp_path: Path, kind: str) -> None:
    source = declaration(tmp_path, kind, "Pictures/asset.png")
    document = OdfDocument.open(source)
    document.storage.write_member("Pictures/asset.png", b"asset")
    node = document.edit(Part.CONTENT).find(".//" + qn("form", kind.removeprefix("form-")))
    assert node is not None
    node.set(qn("xlink", "href"), "https://example.test/operate")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == 0
    require_native_context(reopened)


@pytest.mark.parametrize("kind", ["template", "auto-reload"])
def test_metadata_template_provenance_differs_from_replacement_document(
    tmp_path: Path, kind: str
) -> None:
    source = make_package(tmp_path, "text")
    document = OdfDocument.open(source)
    parent = document.edit(Part.META).find(qn("office", "meta"))
    assert parent is not None
    node = etree.SubElement(parent, qn("meta", kind))
    node.set(qn("xlink", "type"), "simple")
    node.set(qn("xlink", "href"), "https://example.test/document.odt")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == (kind == "auto-reload")


@pytest.mark.parametrize("href", [None, ".", "..", "https://example.test/data.odt", "missing.odt"])
def test_chart_self_data_is_a_context_not_an_image_file(tmp_path: Path, href: str | None) -> None:
    body = (
        '<office:chart><chart:chart xmlns:chart="urn:oasis:names:tc:opendocument:xmlns:chart:1.0" '
        'chart:class="chart:bar" svg:width="5cm" svg:height="5cm" '
        f'xlink:type="simple" xlink:href="{href}"><chart:plot-area/></chart:chart></office:chart>'
    )
    source = make_package(
        tmp_path,
        "text",
        Variant(body=body, media_type="application/vnd.oasis.opendocument.chart", extension=".odc"),
    )
    document = OdfDocument.open(source)
    if href is None:
        node = document.edit(Part.CONTENT).find(".//" + qn("chart", "chart"))
        assert node is not None
        node.attrib.pop(qn("xlink", "href"))
        node.attrib.pop(qn("xlink", "type"))
        document.save(source)
        document = OdfDocument.open(source)
    assert validate(document).count == 0
    assert native_export_limitations(document)["rendering_dependencies"] == (href != ".")


@pytest.mark.parametrize("href", ["macro-library/code", "https://example.test/code"])
def test_script_uri_loading_is_unestablished_even_for_present_internal_bytes(
    tmp_path: Path, href: str
) -> None:
    body = (
        "<office:text><text:p><text:script "
        'xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" '
        f'script:language="JavaScript" xlink:type="simple" xlink:href="{href}"/>'
        "</text:p></office:text>"
    )
    source = make_package(tmp_path, "text", Variant(body=body))
    document = OdfDocument.open(source)
    document.storage.write_member("macro-library/code", b"controlled script")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == 1
    with pytest.raises(ToolFailedError):
        require_native_context(reopened)
