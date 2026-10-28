# SPDX-License-Identifier: MPL-2.0
"""Page mechanics preserve content and require complete, globally unambiguous navigation."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.content import (
    SHAPE_TAGS,
    GraphicAlternative,
    GraphicEditor,
    PageDecision,
    PageEditor,
    page_fingerprint,
    page_shapes,
    page_snapshot,
    pages,
)
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .documents import Variant, make_flat, make_package

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SHAPES = (
    '<draw:frame draw:name="Title" xml:id="title" draw:id="title">'
    "<draw:text-box><text:p>Overview</text:p></draw:text-box></draw:frame>"
    '<draw:rect draw:name="Counts" xml:id="counts" draw:id="counts">'
    "<text:p>Apples 3; Pears 4</text:p></draw:rect>"
)


def _body(family: str) -> str:
    kind = "presentation" if family == "presentation" else "drawing"
    return (
        f'<office:{kind}><draw:page draw:name="Overview" draw:master-page-name="Default">'
        f"{SHAPES}</draw:page></office:{kind}>"
    )


@pytest.mark.parametrize("family", ["presentation", "drawing"])
@pytest.mark.parametrize("make", [make_package, make_flat])
def test_page_and_shape_descriptions_and_navigation_are_schema_valid_and_idempotent(
    tmp_path: Path, family: str, make: Callable[[Path, str, Variant], Path]
) -> None:
    doc = OdfDocument.open(make(tmp_path, family, Variant(body=_body(family))))
    page = pages(doc)[0]
    fingerprint = page_fingerprint(page, doc)
    before = page_snapshot(doc)
    editor = PageEditor(
        {
            "Overview": PageDecision(
                "Fruit overview", "Invented fruit counts", ("title", "counts"), fingerprint
            )
        },
        "set_pages",
    )
    assert editor.apply(doc)[0].status is Status.APPLIED
    assert editor.apply(doc)[0].status is Status.UNCHANGED
    graphics = GraphicEditor(
        {"Counts": GraphicAlternative("Counts", "Three apples and four pears")},
        "set_graphics",
        SHAPE_TAGS,
    )
    assert graphics.apply(doc)[0].status is Status.APPLIED
    assert graphics.apply(doc)[0].status is Status.UNCHANGED
    assert page_snapshot(doc) == before
    assert page_fingerprint(page, doc) == fingerprint
    assert validate(doc).count == 0
    assert [shape.get(qn("draw", "name")) for shape in page_shapes(page)] == ["Title", "Counts"]


@pytest.mark.parametrize(
    "order", [("title",), ("title", "title"), ("counts", "unknown"), ("title counts",)]
)
def test_partial_duplicate_unknown_or_malformed_navigation_is_rejected(
    tmp_path: Path, order: tuple[str, ...]
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=_body("drawing"))))
    original = etree.tostring(doc.tree(Part.CONTENT))
    editor = PageEditor(
        {"Overview": PageDecision(title="Must not be written", navigation=order)}, "set_pages"
    )
    assert editor.apply(doc)[0].status is Status.FAILED
    assert etree.tostring(doc.tree(Part.CONTENT)) == original
    assert not doc.dirty


def test_a_duplicate_identity_on_another_page_is_rejected(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=_body("drawing"))))
    page = pages(doc)[0]
    second = deepcopy(page)
    second.set(qn("draw", "name"), "Other")
    parent = page.getparent()
    assert parent is not None
    parent.append(second)
    editor = PageEditor({"Overview": PageDecision(navigation=("counts", "title"))}, "set_pages")
    checkpoint = doc.checkpoint()
    assert editor.apply(doc)[0].status is Status.FAILED
    assert not doc.changed_since(checkpoint)


def test_hyperlink_wrapping_does_not_hide_a_top_level_shape(tmp_path: Path) -> None:
    body = (
        _body("drawing")
        .replace("<draw:rect ", '<draw:a xlink:href="https://example.org"><draw:rect ')
        .replace("</draw:rect>", "</draw:rect></draw:a>")
    )
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=body)))
    assert len(page_shapes(pages(doc)[0])) == 2
    incomplete = PageEditor({"Overview": PageDecision(navigation=("title",))}, "set_pages")
    assert incomplete.apply(doc)[0].status is Status.FAILED


@pytest.mark.parametrize("attribute", [("svg", "x"), ("xlink", "href"), ("draw", "name")])
def test_protected_snapshot_detects_geometry_identity_and_reference_damage(
    tmp_path: Path, attribute: tuple[str, str]
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=_body("drawing"))))
    before = page_snapshot(doc)
    shape = select_elements(doc.tree(Part.CONTENT), "//draw:rect")[0]
    shape.set(qn(*attribute), "changed")
    assert page_snapshot(doc) != before


@pytest.mark.parametrize("make", [make_package, make_flat])
@pytest.mark.parametrize("display", ["always", "none", "printer"])
def test_hidden_layer_declarations_are_counted_once_across_logical_views(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path], display: str
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=_body("drawing"))))
    layer_set = etree.Element(qn("draw", "layer-set"))
    pages(document)[0].insert(0, layer_set)
    etree.SubElement(
        layer_set,
        qn("draw", "layer"),
        {
            qn("draw", "name"): "Review layer",
            qn("draw", "display"): display,
        },
    )
    source = document.save(tmp_path / ("layers" + document.storage.source.suffix))
    assert validate(OdfDocument.open(source)).count == 0
    findings = [f for f in audit_odf(source).findings if f.rule_id == "DRAW007"]
    if display == "always":
        assert findings == []
    else:
        assert len(findings) == 1
        assert findings[0].details == {"hidden_layer_declarations": 1}
