# SPDX-License-Identifier: MPL-2.0
"""Page mechanics preserve content and require complete, globally unambiguous navigation."""

from copy import deepcopy
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.concepts import page_fingerprint, page_shapes, pages
from odfa11y.decisions.edit import Status
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.rules import registry as rules
from tests.fixtures.answers import (
    apply_in_memory,
    graphic_answer,
    graphic_inputs,
    page_answer,
    page_inputs,
)
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import apply_answers

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
    before = tuple(page_fingerprint(page, doc) for page in pages(doc))
    editor = page_inputs({
        "Overview": page_answer(
            "Fruit overview", "Invented fruit counts", ("title", "counts"), fingerprint
        )
    })
    assert apply_in_memory(doc, editor)[0].status is Status.APPLIED
    assert apply_in_memory(doc, editor)[0].status is Status.UNCHANGED
    graphics = graphic_inputs({"Counts": graphic_answer("Counts", "Three apples and four pears")})
    assert apply_in_memory(doc, graphics)[0].status is Status.APPLIED
    assert apply_in_memory(doc, graphics)[0].status is Status.UNCHANGED
    assert tuple(page_fingerprint(page, doc) for page in pages(doc)) == before
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
    source = doc.save(tmp_path / "reviewed.odg")
    before = source.read_bytes()
    destination = tmp_path / "refused.odg"
    editor = page_inputs({"Overview": page_answer(title="Must not be written", navigation=order)})
    result = apply_answers(source, destination, [editor])
    assert not result.published
    assert any(outcome.status is Status.FAILED for outcome in result.outcomes)
    assert source.read_bytes() == before
    assert not destination.exists()


def test_a_duplicate_identity_on_another_page_is_rejected(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=_body("drawing"))))
    page = pages(doc)[0]
    second = deepcopy(page)
    second.set(qn("draw", "name"), "Other")
    parent = page.getparent()
    assert parent is not None
    parent.append(second)
    editor = page_inputs({"Overview": page_answer(navigation=("counts", "title"))})
    checkpoint = doc.checkpoint()
    assert apply_in_memory(doc, editor)[0].status is Status.FAILED
    assert not doc.changed_since(checkpoint)


def test_hyperlink_wrapping_does_not_hide_a_top_level_shape(tmp_path: Path) -> None:
    body = (
        _body("drawing")
        .replace("<draw:rect ", '<draw:a xlink:href="https://example.org"><draw:rect ')
        .replace("</draw:rect>", "</draw:rect></draw:a>")
    )
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=body)))
    assert len(page_shapes(pages(doc)[0])) == 2
    incomplete = page_inputs({"Overview": page_answer(navigation=("title",))})
    assert apply_in_memory(doc, incomplete)[0].status is Status.FAILED


@pytest.mark.parametrize("attribute", [("svg", "x"), ("xlink", "href"), ("draw", "name")])
def test_protected_snapshot_detects_geometry_identity_and_reference_damage(
    tmp_path: Path, attribute: tuple[str, str]
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "drawing", Variant(body=_body("drawing"))))
    before = tuple(page_fingerprint(page, doc) for page in pages(doc))
    shape = select_elements(doc.tree(Part.CONTENT), "//draw:rect")[0]
    shape.set(qn(*attribute), "changed")
    assert tuple(page_fingerprint(page, doc) for page in pages(doc)) != before


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
    findings = [f for f in audit_odf(source).findings if f.rule_id == rules.ORDER003.id]
    if display == "always":
        assert findings == []
    else:
        assert len(findings) == 1
        assert findings[0].details == {"hidden_layer_declarations": 1}
