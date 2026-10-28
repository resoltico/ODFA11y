# SPDX-License-Identifier: MPL-2.0
"""Reviewed graphic roles and normative link descriptions protect their source boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import (
    GraphicAlternative,
    LinkDescription,
    PageDecision,
    graphics_fingerprint,
    page_fingerprint,
    pages,
)
from odfa11y.content.links import link_fingerprint, link_location
from odfa11y.errors import PlanError
from odfa11y.families import image, spreadsheet, text
from odfa11y.families import pages as page_family
from odfa11y.families.text import SetLinkDescriptions
from odfa11y.odf import NS, OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans import load_plan
from odfa11y.remediation.planning import compile_operations

from .documents import Variant, make_flat, make_package
from .graphic_fixtures import _style
from .operation_execution import execute_operations
from .reviewed_plans import plan_header
from .test_graphic_roles_links import _graphic

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("family", ["presentation", "drawing"])
def test_page_graphic_and_legal_link_metadata_compose_and_reapply(
    tmp_path: Path, family: str
) -> None:
    kind = "presentation" if family == "presentation" else "drawing"
    body = (
        f'<office:{kind}><draw:page draw:name="Overview" draw:master-page-name="Default">'
        '<draw:a xml:id="guide" xlink:type="simple" xlink:href="https://example.test/">'
        '<draw:rect draw:name="Diagram" svg:width="2cm" svg:height="2cm"/></draw:a>'
        '<draw:rect draw:name="Decoration" svg:width="1cm" svg:height="1cm"/>'
        f"</draw:page></office:{kind}>"
    )
    source = make_flat(tmp_path, family, Variant(body=body))
    document = OdfDocument.open(source)
    _style(document, "Visual")
    target = select_elements(document.tree(Part.CONTENT), "//draw:rect[@draw:name='Decoration']")[0]
    target.set(qn("draw", "style-name"), "Visual")
    document.save(source)
    adapter = page_family
    page = pages(document)[0]
    link = select_elements(document.tree(Part.CONTENT), "//draw:a")[0]
    shape = select_elements(document.tree(Part.CONTENT), "//draw:rect[@draw:name='Diagram']")[0]
    decoration = select_elements(
        document.tree(Part.CONTENT), "//draw:rect[@draw:name='Decoration']"
    )[0]
    operations = [
        adapter.SetPageSemantics({
            "Overview": PageDecision(title="Overview", fingerprint=page_fingerprint(page, document))
        }),
        adapter.SetGraphicAlternatives({
            "Diagram": GraphicAlternative(
                description="A contextual diagram",
                fingerprint=graphics_fingerprint(document, [shape]),
            ),
            "Decoration": GraphicAlternative(
                decorative=True, fingerprint=graphics_fingerprint(document, [decoration])
            ),
        }),
        adapter.SetLinkDescriptions({
            link_location(link, 1).path: LinkDescription(
                "Read the guide", link_fingerprint(document, link)
            )
        }),
    ]
    output = tmp_path / ("0123456789abcdef" + source.suffix)

    first = execute_operations(source, output, operations)
    assert first.changed
    assert validate(OdfDocument.open(output)).count == 0
    repeated = execute_operations(output, tmp_path / "repeated.fodg", operations)
    assert not repeated.changed


def test_link_identity_encoding_context_and_repeat_refusal(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    parent = frame.getparent()
    assert parent is not None
    link = etree.SubElement(
        parent,
        qn("draw", "a"),
        {
            "{http://www.w3.org/XML/1998/namespace}id": "café",
            qn("xlink", "href"): "https://example.test/",
        },
    )
    assert link_location(link, 1).path == "content/link[id=caf%C3%A9]"
    description = LinkDescription("Read the guide", link_fingerprint(document, link))
    operation = SetLinkDescriptions({link_location(link, 1).path: description})
    duplicate = etree.SubElement(
        parent, qn("draw", "rect"), {"{http://www.w3.org/XML/1998/namespace}id": "café"}
    )
    assert operation.apply(document)[0].status == Status.FAILED
    parent.remove(duplicate)
    assert operation.apply(document)[0].status == Status.APPLIED


@pytest.mark.parametrize("family", ["text", "spreadsheet", "presentation", "drawing"])
def test_family_link_configuration_requires_review_and_reaches_operations(
    tmp_path: Path, family: str
) -> None:
    source = make_package(tmp_path, family)
    header = plan_header(source)
    config = tmp_path / "links.toml"
    config.write_text(
        header + '[decisions."link.description"."content/link[1]"]\n'
        'description = "Read the guide"\nfingerprint = "0123456789abcdef"\n',
        encoding="utf-8",
    )
    [operation] = compile_operations(OdfDocument.open(source), load_plan(config))
    assert isinstance(
        operation,
        (
            text.SetLinkDescriptions,
            spreadsheet.SetLinkDescriptions,
            page_family.SetLinkDescriptions,
        ),
    )
    assert operation.name == "set_link_descriptions"
    assert operation.entries["content/link[1]"] == LinkDescription(
        "Read the guide", "0123456789abcdef"
    )
    for invalid in (
        'description = ""\nfingerprint = "0123456789abcdef"',
        'description = "Read the guide"',
        'description = "Read the guide"\nfingerprint = false',
        'description = "Read the guide"\nfingerprint = "0123456789abcdef"\nname = "Target"',
    ):
        config.write_text(
            header + f'[decisions."link.description"."content/link[1]"]\n{invalid}\n',
            encoding="utf-8",
        )
        with pytest.raises(PlanError):
            load_plan(config)


@pytest.mark.parametrize("family", ["text", "spreadsheet", "presentation", "drawing", "image"])
def test_family_role_configuration_uses_exact_booleans(tmp_path: Path, family: str) -> None:
    source = make_package(tmp_path, family)
    header = plan_header(source)
    config = tmp_path / "roles.toml"
    config.write_text(
        header
        + (
            '[decisions."graphic.alternative"."content/frame[name=Picture]"]\n'
            "decorative = true\n"
            'fingerprint = "0123456789abcdef"\n'
        ),
        encoding="utf-8",
    )
    [operation] = compile_operations(OdfDocument.open(source), load_plan(config))
    assert isinstance(
        operation,
        (
            text.SetGraphicAlternatives,
            spreadsheet.SetGraphicAlternatives,
            page_family.SetGraphicAlternatives,
            image.SetGraphicAlternatives,
        ),
    )
    assert operation.name == "set_graphic_alternatives"
    assert operation.entries["content/frame[name=Picture]"].decorative is True
    for invalid in ("1", '"true"', "[true]"):
        config.write_text(
            header
            + '[decisions."graphic.alternative"."content/frame[name=Picture]"]\n'
            + f"decorative = {invalid}\n"
            + 'fingerprint = "0123456789abcdef"\n',
            encoding="utf-8",
        )
        with pytest.raises(PlanError):
            load_plan(config)


def test_unstyled_restoration_refuses_and_styled_role_composes_under_decorative_default(
    tmp_path: Path,
) -> None:
    document, frame = _graphic(tmp_path)
    root = document.tree(Part.STYLES).getroot()
    common = root.find("office:styles", NS)
    assert common is not None
    default = etree.SubElement(
        common, qn("style", "default-style"), {qn("style", "family"): "graphic"}
    )
    etree.SubElement(
        default,
        qn("style", "graphic-properties"),
        {qn("draw", "decorative"): "true", qn("draw", "fill-color"): "#112233"},
    )
    document.tree(Part.CONTENT)
    parent = frame.getparent()
    assert parent is not None
    parent.remove(frame)
    link = etree.SubElement(
        parent,
        qn("draw", "a"),
        {
            qn("xlink", "href"): "https://example.test/",
            qn("xlink", "type"): "simple",
            "{http://www.w3.org/XML/1998/namespace}id": "guide",
        },
    )
    link.append(frame)
    reviewed = link_fingerprint(document, link)
    graphics = text.SetGraphicAlternatives({
        "Logo": GraphicAlternative(
            decorative=False,
            description="A meaningful logo",
            fingerprint=graphics_fingerprint(document, [frame]),
        )
    })
    links = text.SetLinkDescriptions({
        link_location(link, 1).path: LinkDescription("Read the guide", reviewed)
    })
    checkpoint = document.checkpoint()
    assert graphics.apply(document)[0].status == Status.FAILED
    assert not document.changed_since(checkpoint)
    _style(document, "Visual")
    frame.set(qn("draw", "style-name"), "Visual")
    reviewed = link_fingerprint(document, link)
    graphics = text.SetGraphicAlternatives({
        "Logo": GraphicAlternative(
            decorative=False,
            description="A meaningful logo",
            fingerprint=graphics_fingerprint(document, [frame]),
        )
    })
    links = text.SetLinkDescriptions({
        link_location(link, 1).path: LinkDescription("Read the guide", reviewed)
    })
    assert graphics.apply(document)[0].status == Status.APPLIED
    assert link_fingerprint(document, link) == reviewed
    assert links.apply(document)[0].status == Status.APPLIED
    assert graphics.apply(document)[0].status == Status.UNCHANGED
    assert links.apply(document)[0].status == Status.UNCHANGED
    assert validate(document).count == 0


def test_graphic_payload_drift_invalidates_link_review(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    parent = frame.getparent()
    assert parent is not None
    parent.remove(frame)
    link = etree.SubElement(parent, qn("draw", "a"), {qn("xlink", "href"): "https://example.test/"})
    link.append(frame)
    operation = SetLinkDescriptions({
        link_location(link, 1).path: LinkDescription(
            "Read the guide", link_fingerprint(document, link)
        )
    })
    document.storage.write_member("Pictures/logo.svg", b"changed payload")
    assert operation.apply(document)[0].status == Status.FAILED
