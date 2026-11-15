# SPDX-License-Identifier: MPL-2.0
"""Reviewed group, link and page metadata binds descendant graphic style definitions."""

from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.concepts import graphics_fingerprint
from odfa11y.concepts.links import link_fingerprint, link_location
from odfa11y.concepts.pages import page_fingerprint, pages
from odfa11y.decisions.edit import Status
from odfa11y.errors import PlanError
from odfa11y.odf import NS, OdfDocument, Part, qn, select_elements, validate
from tests.fixtures.answers import (
    graphic_answer,
    graphic_inputs,
    link_answer,
    link_inputs,
    page_answer,
    page_inputs,
)
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.graphics import _style
lazy from tests.fixtures.answers import apply_in_memory

BODY = (
    '<office:drawing><draw:page draw:name="Overview" draw:master-page-name="Default">'
    '<draw:a xml:id="guide" xlink:type="simple" xlink:href="https://example.test/">'
    '<draw:g draw:name="Group"><draw:g draw:name="Nested">'
    '<draw:frame draw:name="Leaf" draw:style-name="Visual" svg:width="1cm" svg:height="1cm">'
    "<draw:image><office:binary-data>"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
    "</office:binary-data></draw:image><svg:title>Authored leaf</svg:title></draw:frame>"
    "</draw:g></draw:g></draw:a></draw:page></office:drawing>"
)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_nested_graphic_visual_drift_rejects_leaf_link_and_page_decisions(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=BODY)))
    visual = _style(document, "Visual")
    leaf = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    link = select_elements(document.tree(Part.CONTENT), "//draw:a")[0]
    page = pages(document)[0]
    assert validate(document).count == 0
    graphic = graphics_fingerprint(document, [leaf])
    hyperlink = link_fingerprint(document, link)
    overview = page_fingerprint(page, document)
    operations = [
        graphic_inputs({"Leaf": graphic_answer(description="Reviewed leaf", fingerprint=graphic)}),
        link_inputs({link_location(link, 1).path: link_answer("Read the guide", hyperlink)}),
        page_inputs({"Overview": page_answer(title="Reviewed page", fingerprint=overview)}),
    ]
    properties = visual.find("style:graphic-properties", NS)
    assert properties is not None
    properties.set(qn("draw", "fill-color"), "#ffffff")
    assert validate(document).count == 0
    assert graphics_fingerprint(document, [leaf]) != graphic
    assert link_fingerprint(document, link) != hyperlink
    assert page_fingerprint(page, document) != overview
    before = document.checkpoint()
    for operation in operations:
        with pytest.raises(PlanError, match="fingerprint"):
            apply_in_memory(document, operation)
    assert not document.changed_since(before)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_nested_graphic_metadata_and_proven_role_derivation_reapply(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=BODY)))
    _style(document, "Visual", role="true")
    leaf = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    link = select_elements(document.tree(Part.CONTENT), "//draw:a")[0]
    page = pages(document)[0]
    operations = [
        graphic_inputs({
            "Leaf": graphic_answer(
                decorative=False, fingerprint=graphics_fingerprint(document, [leaf])
            ),
        }),
        link_inputs({
            link_location(link, 1).path: link_answer(
                "Read the guide", link_fingerprint(document, link)
            )
        }),
        page_inputs({
            "Overview": page_answer(
                title="Reviewed page", fingerprint=page_fingerprint(page, document)
            )
        }),
    ]
    for operation in operations:
        assert all(
            outcome.status == Status.APPLIED for outcome in apply_in_memory(document, operation)
        )
    assert validate(document).count == 0
    for operation in operations:
        assert all(
            outcome.status == Status.UNCHANGED for outcome in apply_in_memory(document, operation)
        )


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_page_visual_style_definition_is_also_bound(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=BODY)))
    _style(document, "Visual")
    page_style = _style(document, "PageVisual")
    page_style.set(qn("style", "family"), "drawing-page")
    properties = page_style.find("style:graphic-properties", NS)
    assert properties is not None
    page_style.remove(properties)
    properties = etree.SubElement(
        page_style, qn("style", "drawing-page-properties"), {qn("draw", "fill-color"): "#112233"}
    )
    page = pages(document)[0]
    page.set(qn("draw", "style-name"), "PageVisual")
    assert validate(document).count == 0
    operation = page_inputs({
        "Overview": page_answer(title="Reviewed page", fingerprint=page_fingerprint(page, document))
    })
    properties.set(qn("draw", "fill-color"), "#ffffff")
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(document, operation)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_valid_conditional_graphic_style_context_refuses_all_reviewed_metadata(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=BODY)))
    visual = _style(document, "Visual")
    alternate = _style(document, "Alternate")
    etree.SubElement(
        visual,
        qn("style", "map"),
        {
            qn("style", "condition"): "cell-content()=1",
            qn("style", "apply-style-name"): "Alternate",
        },
    )
    assert validate(document).count == 0
    leaf = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    link = select_elements(document.tree(Part.CONTENT), "//draw:a")[0]
    page = pages(document)[0]
    properties = alternate.find("style:graphic-properties", NS)
    assert properties is not None
    properties.set(qn("draw", "fill-color"), "#ffffff")
    assert validate(document).count == 0
    operations = [
        graphic_inputs({
            "Leaf": graphic_answer(
                description="Reviewed leaf", fingerprint=graphics_fingerprint(document, [leaf])
            )
        }),
        link_inputs({
            link_location(link, 1).path: link_answer(
                "Read the guide", link_fingerprint(document, link)
            )
        }),
        page_inputs({
            "Overview": page_answer(
                title="Reviewed page", fingerprint=page_fingerprint(page, document)
            )
        }),
    ]
    before = document.checkpoint()
    for operation in operations:
        outcomes = apply_in_memory(document, operation)
        assert outcomes[0].status == Status.FAILED
        assert "Conditional graphic style mapping is not established" in outcomes[0].message
    assert not document.changed_since(before)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_scene_review_binds_visual_styles_of_nested_three_dimensional_objects(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    body = (
        '<office:drawing><draw:page draw:name="Overview" draw:master-page-name="Default">'
        '<dr3d:scene xmlns:dr3d="urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0" '
        'draw:name="Scene"><dr3d:cube draw:style-name="Visual"/>'
        "</dr3d:scene></draw:page></office:drawing>"
    )
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=body)))
    visual = _style(document, "Visual")
    scene = next(document.tree(Part.CONTENT).iter(qn("dr3d", "scene")))
    assert validate(document).count == 0
    operation = graphic_inputs({
        "Scene": graphic_answer(
            description="Reviewed scene", fingerprint=graphics_fingerprint(document, [scene])
        )
    })
    properties = visual.find("style:graphic-properties", NS)
    assert properties is not None
    properties.set(qn("draw", "fill-color"), "#ffffff")
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(document, operation)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_page_style_conditional_mapping_refuses_reviewed_metadata(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    document = OdfDocument.open(make(tmp_path, "drawing", Variant(body=BODY)))
    _style(document, "Visual")
    page_style = _style(document, "PageVisual")
    page_style.set(qn("style", "family"), "drawing-page")
    properties = page_style.find("style:graphic-properties", NS)
    assert properties is not None
    page_style.remove(properties)
    etree.SubElement(page_style, qn("style", "drawing-page-properties"))
    etree.SubElement(
        page_style,
        qn("style", "map"),
        {
            qn("style", "condition"): "cell-content()=1",
            qn("style", "apply-style-name"): "PageVisual",
        },
    )
    page = pages(document)[0]
    page.set(qn("draw", "style-name"), "PageVisual")
    assert validate(document).count == 0
    operation = page_inputs({
        "Overview": page_answer(title="Reviewed page", fingerprint=page_fingerprint(page, document))
    })
    before = document.checkpoint()
    outcome = apply_in_memory(document, operation)[0]
    assert outcome.status == Status.FAILED
    assert "Conditional graphic style mapping is not established" in outcome.message
    assert not document.changed_since(before)
