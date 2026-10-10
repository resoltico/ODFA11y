# SPDX-License-Identifier: MPL-2.0
"""Supported Draw fills and Writer image bullets retain independently known pixels."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.cli import main
from odfa11y.content import require_native_context
from odfa11y.odf import OdfDocument, Part, qn, validate

from .native_resource_fixtures import (
    PIXELS,
    decoded_images,
    png_bytes,
    writer_resource,
)
from .resource_declaration_fixtures import declaration

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration


def _writer_bullets(directory: Path) -> Path:
    source = writer_resource(directory)
    document = OdfDocument.open(source)
    root = document.edit(Part.CONTENT).getroot()
    styles = etree.Element(qn("office", "styles"))
    meta = root.find(qn("office", "meta"))
    assert meta is not None
    root.insert(root.index(meta) + 1, styles)
    style = etree.SubElement(styles, qn("text", "list-style"))
    style.set(qn("style", "name"), "ImageBullets")
    level = etree.SubElement(style, qn("text", "list-level-style-image"))
    level.set(qn("text", "level"), "1")
    etree.SubElement(level, qn("office", "binary-data")).text = base64.b64encode(
        png_bytes()
    ).decode()
    props = etree.SubElement(level, qn("style", "list-level-properties"))
    props.set(qn("fo", "width"), "0.5cm")
    props.set(qn("fo", "height"), "0.5cm")
    props.set(qn("text", "space-before"), "0cm")
    props.set(qn("text", "min-label-width"), "0.5cm")
    body = root.find(".//" + qn("office", "text"))
    assert body is not None
    # Remove the ordinary image: only the bullet can satisfy the pixel oracle.
    body[:] = []
    listing = etree.SubElement(body, qn("text", "list"))
    listing.set(qn("text", "style-name"), "ImageBullets")
    item = etree.SubElement(listing, qn("text", "list-item"))
    etree.SubElement(item, qn("text", "p")).text = "Sentinel image bullet"
    return document.save(source)


@pytest.mark.parametrize("kind", ["fill", "bullet"])
def test_real_native_declaration_renders_the_expected_asset(
    tmp_path: Path, external_tool: Callable[..., str], kind: str
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    if kind == "fill":
        source = declaration(tmp_path, "fill", "Pictures/control.png", active=True)
        document = OdfDocument.open(source)
        document.storage.write_member("Pictures/control.png", png_bytes())
        manifest = document.edit(Part.MANIFEST)
        entry = etree.SubElement(manifest.getroot(), qn("manifest", "file-entry"))
        entry.set(qn("manifest", "full-path"), "Pictures/control.png")
        entry.set(qn("manifest", "media-type"), "image/png")
        document.save(source)
    else:
        source = _writer_bullets(tmp_path)
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    require_native_context(document)
    destination = tmp_path / "native.pdf"
    assert main(["export", str(source), str(destination), "--soffice", soffice]) == 0
    assert ((4, 4), PIXELS) in decoded_images(destination)
    assert not list(tmp_path.glob(".odfa11y-source-*"))
