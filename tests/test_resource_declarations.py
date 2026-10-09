# SPDX-License-Identifier: MPL-2.0
"""Declaration recognition and addressing have independent schema/audit/refusal oracles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.content import native_export_limitations, require_native_context
from odfa11y.errors import ToolFailedError
from odfa11y.odf import OdfDocument, Part, qn, validate

from .resource_declaration_fixtures import declaration

if TYPE_CHECKING:
    from pathlib import Path

KINDS = ["fill", "bullet", "symbol", "font", "form-button", "form-image", "form-image-frame"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("href", ["https://example.test/asset.png", "assets/local.png"])
def test_schema_valid_declarations_are_reported_and_refused(
    tmp_path: Path, kind: str, href: str
) -> None:
    source = declaration(tmp_path, kind, href)
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    report = audit_odf(source)
    assert "ODF012" in {f.rule_id for f in report.findings}
    assert report.metadata["native_export_limitations"]["rendering_dependencies"] == 1
    with pytest.raises(ToolFailedError, match="rendering dependencies"):
        require_native_context(document)


@pytest.mark.parametrize("kind", ["fill", "bullet", "symbol", "font", "form-image"])
@pytest.mark.parametrize("base", ["direct", "inherited"])
def test_internal_reference_with_explicit_base_is_unestablished(
    tmp_path: Path, kind: str, base: str
) -> None:
    source = declaration(tmp_path, kind, "Pictures/asset.png")
    document = OdfDocument.open(source)
    document.storage.write_member("Pictures/asset.png", b"controlled bytes")
    attribute = qn("form", "image-data") if kind == "form-image" else qn("xlink", "href")
    document.edit(Part.CONTENT)
    document.edit(Part.STYLES)
    nodes = [
        n
        for tree in document.distinct_trees(Part.CONTENT, Part.STYLES)
        for n in tree.iter()
        if n.get(attribute) == "Pictures/asset.png"
    ]
    assert len(nodes) == 1
    node = nodes[0] if base == "direct" else nodes[0].getparent()
    assert node is not None
    node.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/")
    document.save(source)
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 1


@pytest.mark.parametrize("kind", KINDS)
def test_exact_internal_percent_escaped_file_with_fragment_is_supported(
    tmp_path: Path, kind: str
) -> None:
    source = declaration(tmp_path, kind, "Pictures/asset%20name.png#item")
    document = OdfDocument.open(source)
    document.storage.write_member("Pictures/asset name.png", b"controlled bytes")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == 0
    require_native_context(reopened)


@pytest.mark.parametrize("kind", ["fill", "bullet", "image", "object-ole"])
def test_inline_binary_data_does_not_create_a_uri_dependency(tmp_path: Path, kind: str) -> None:
    source = declaration(tmp_path, kind, None)
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    require_native_context(document)
    assert native_export_limitations(document)["rendering_dependencies"] == 0


@pytest.mark.parametrize(
    "href",
    [
        ".",
        "./",
        "Pictures",
        "Pictures/",
        "Empty/",
        "file.png/",
        "file.png%2f",
        "file.png/.",
        "Pictures%2F",
    ],
)
@pytest.mark.parametrize("kind", ["image", "fill", "object-ole"])
def test_file_resources_reject_root_directories_and_directory_intent(
    tmp_path: Path, href: str, kind: str
) -> None:
    source = declaration(tmp_path, kind, href)
    document = OdfDocument.open(source)
    document.storage.write_member("Pictures/child.png", b"asset")
    document.storage.write_member("Pictures/content.xml", b"object document")
    document.storage.write_member("Empty/", b"")
    document.storage.write_member("file.png", b"asset")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == 1
    with pytest.raises(ToolFailedError):
        require_native_context(reopened)


@pytest.mark.parametrize("href", ["Object1", "Object1/", "Object1%2F", "object.odt"])
def test_embedded_object_contract_accepts_subdocument_folders_and_separate_files(
    tmp_path: Path, href: str
) -> None:
    source = declaration(tmp_path, "object", href)
    document = OdfDocument.open(source)
    document.storage.write_member("Object1/content.xml", b"opaque subdocument bytes")
    document.storage.write_member("object.odt", b"opaque package bytes")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    require_native_context(reopened)
