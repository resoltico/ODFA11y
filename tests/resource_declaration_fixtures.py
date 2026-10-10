# SPDX-License-Identifier: MPL-2.0
"""Schema-defined declaration fixtures with real package members and inline image data."""

from __future__ import annotations

import base64
from pathlib import Path

from lxml import etree

from odfa11y.content import GraphicDescription, PageDecision
from odfa11y.families.drawing import SetGraphicDescriptions, SetPageSemantics
from odfa11y.odf import OdfDocument, Part, qn
from odfa11y.remediation import SetMetadata

from .native_resource_fixtures import png_bytes

DRAWING = Path(__file__).parent / "family_corpus" / "fruit-drawing.odg"


def declaration(directory: Path, kind: str, href: str | None, *, active: bool = False) -> Path:
    """Build a real drawing with a declared image/resource target.

    Returns
    -------
    Path
        Saved ODF package; inline binary data is used when href is absent.

    """
    document = OdfDocument.open(DRAWING)
    for operation in [
        SetMetadata(language="en-GB"),
        SetGraphicDescriptions({
            "Fruit illustration": GraphicDescription(description="Fruit drawing")
        }),
        SetPageSemantics({"Fruit overview": PageDecision(title="Fruit overview")}),
    ]:
        operation.apply(document)
    node = (
        _style_resource(document, kind, active=active)
        if kind in {"fill", "bullet", "symbol", "font"}
        else _content_resource(document, kind)
    )
    if href is None:
        for name in ["href", "type", "show", "actuate"]:
            node.attrib.pop(qn("xlink", name), None)
        etree.SubElement(node, qn("office", "binary-data")).text = base64.b64encode(
            png_bytes()
        ).decode()
    elif kind.startswith("form-"):
        node.set(qn("form", "image-data"), href)
    else:
        if kind != "symbol":
            node.set(qn("xlink", "type"), "simple")
        node.set(qn("xlink", "href"), href)
    return document.save(directory / (kind + ".odg"))


def _style_resource(document: OdfDocument, kind: str, *, active: bool) -> etree._Element:
    styles = document.edit(Part.STYLES)
    parent = styles.find(qn("office", "styles"))
    assert parent is not None
    if kind == "fill":
        node = etree.SubElement(parent, qn("draw", "fill-image"))
        node.set(qn("draw", "name"), "ControlFill")
        if active:
            properties = document.edit(Part.CONTENT).find(".//" + qn("style", "graphic-properties"))
            assert properties is not None
            properties.set(qn("draw", "fill"), "bitmap")
            properties.set(qn("draw", "fill-image-name"), "ControlFill")
    elif kind == "bullet":
        style = etree.SubElement(parent, qn("text", "list-style"))
        style.set(qn("style", "name"), "ControlBullets")
        node = etree.SubElement(style, qn("text", "list-level-style-image"))
        node.set(qn("text", "level"), "1")
    elif kind == "symbol":
        style = etree.SubElement(parent, qn("style", "style"))
        style.set(qn("style", "name"), "ControlChart")
        style.set(qn("style", "family"), "chart")
        properties = etree.SubElement(style, qn("style", "chart-properties"))
        properties.set(qn("chart", "symbol-type"), "image")
        node = etree.SubElement(properties, qn("chart", "symbol-image"))
    elif kind == "font":
        parent = styles.find(qn("office", "font-face-decls"))
        assert parent is not None
        font = etree.SubElement(parent, qn("style", "font-face"))
        font.set(qn("style", "name"), "ControlFont")
        node = etree.SubElement(font, qn("svg", "definition-src"))
    return node


def _content_resource(document: OdfDocument, kind: str) -> etree._Element:
    if kind.startswith("form-"):
        page = document.edit(Part.CONTENT).find(".//" + qn("draw", "page"))
        assert page is not None
        forms = etree.Element(qn("office", "forms"))
        before_shapes = next(
            (
                i
                for i, child in enumerate(page)
                if child.tag not in {qn("svg", "title"), qn("svg", "desc"), qn("draw", "layer-set")}
            ),
            len(page),
        )
        page.insert(before_shapes, forms)
        form = etree.SubElement(forms, qn("form", "form"))
        form.set(qn("form", "name"), "ControlForm")
        node = etree.SubElement(form, qn("form", kind.removeprefix("form-")))
        node.set(qn("form", "name"), "ControlImage")
        node.set(qn("form", "id"), "control-image")
        node.set("{http://www.w3.org/XML/1998/namespace}id", "control-image")
    else:
        node = document.edit(Part.CONTENT).find(".//" + qn("draw", "image"))
        assert node is not None
        node.tag = qn("draw", kind)
        node[:] = []
        node.attrib.pop(qn("draw", "mime-type"), None)
    return node
