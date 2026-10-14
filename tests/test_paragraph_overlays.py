# SPDX-License-Identifier: MPL-2.0
"""Unestablished paragraph overlay precedence never authorizes spacing edits."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.errors import RemediationError
from odfa11y.families import style_usage
from odfa11y.families.text import NormalizeSpacing, RemoveEmptySpacers, derived_style_name
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.remediation import remediate

from .documents import Variant, make_flat, make_package

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

STYLES = (
    '<style:style style:name="Base" style:family="paragraph">'
    '<style:paragraph-properties fo:margin-top="0cm"/></style:style>'
    '<style:style style:name="Spacing" style:family="paragraph">'
    '<style:paragraph-properties fo:margin-top="5cm"/></style:style>'
    '<style:style style:name="Break" style:family="paragraph">'
    '<style:paragraph-properties fo:break-before="page"/></style:style>'
    '<style:style style:name="Cycle" style:family="paragraph" style:parent-style-name="Cycle"/>'
    '<style:style style:name="Master" style:family="paragraph" style:master-page-name="Page"/>'
)


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
@pytest.mark.parametrize("position", ["Reference", "Target"])
@pytest.mark.parametrize("classes", ["Spacing", "Break Spacing", "Missing", "Cycle", "Master"])
def test_overlay_on_reference_or_target_refuses_before_mutation(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path], position: str, classes: str
) -> None:
    body = (
        "<office:text>"
        + "".join(
            '<text:p text:style-name="Base"'
            + (f' text:class-names="{classes}"' if text == position else "")
            + f">{text}</text:p>"
            for text in ("Reference", "Target")
        )
        + "</office:text>"
    )
    source = author(tmp_path, "text", Variant(body=body, automatic_styles=STYLES))
    original = source.read_bytes()
    destination = tmp_path / ("existing" + source.suffix)
    destination.write_bytes(b"retain destination")
    report = audit_odf(source)
    assert "TXT062" in {finding.rule_id for finding in report.findings}
    with pytest.raises(RemediationError, match="class overlays"):
        style_usage(source)
    with pytest.raises(RemediationError, match="class overlays"):
        remediate(source, destination, [NormalizeSpacing("Reference", ("Base",))])
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"retain destination"


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
@pytest.mark.parametrize("classes", ["Break", "Master", "Cycle", "Missing"])
def test_break_overlay_is_retained_while_inert_spacer_is_removed(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path], classes: str
) -> None:
    body = (
        f'<office:text><text:p text:style-name="Base" text:class-names="{classes}"/>'
        '<text:p/><text:p text:style-name="Base">Body</text:p></office:text>'
    )
    source = author(tmp_path, "text", Variant(body=body, automatic_styles=STYLES))
    assert validate(OdfDocument.open(source)).count == 0
    before = OdfDocument.open(source).tree(Part.CONTENT)
    original = etree.tostring(select_elements(before, "//text:p[@text:class-names]")[0])
    destination = tmp_path / ("result" + source.suffix)
    assert remediate(source, destination, [RemoveEmptySpacers()]).changed
    after = OdfDocument.open(destination).tree(Part.CONTENT)
    retained = select_elements(after, "//text:p[@text:class-names]")[0]
    assert etree.tostring(retained) == original
    assert retained.get(qn("text", "class-names")) == classes
    assert len(select_elements(after, "//text:p")) == 2


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
@pytest.mark.parametrize("attribute", ["class-names", "cond-style-name"])
@pytest.mark.parametrize("existing", [False, True])
def test_unselected_overlay_consumer_prevents_creating_or_updating_spacing_style(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path], attribute: str, *, existing: bool
) -> None:
    styles = STYLES + (
        '<style:style style:name="One" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="1cm"/></style:style>'
        '<style:style style:name="Two" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="2cm"/></style:style>'
        '<style:style style:name="Other" style:family="paragraph"/>'
    )
    body = (
        '<office:text><text:p text:style-name="One">First reference</text:p>'
        '<text:p text:style-name="Two">Second reference</text:p>'
        '<text:p text:style-name="Base">Target</text:p></office:text>'
    )
    source = author(tmp_path, "text", Variant(body=body, automatic_styles=styles))
    if existing:
        first = tmp_path / ("first" + source.suffix)
        assert remediate(source, first, [NormalizeSpacing("First reference", ("Base",))]).changed
        source = first
    document = OdfDocument.open(source)
    root = select_elements(document.edit(Part.CONTENT), "//office:text")[0]
    consumer = etree.SubElement(root, qn("text", "p"))
    consumer.set(qn("text", "style-name"), "Other")
    consumer.set(qn("text", attribute), derived_style_name("Base"))
    consumer.text = "Unselected consumer"
    source = document.save(tmp_path / ("shared" + source.suffix))
    assert validate(OdfDocument.open(source)).count == 0
    original = source.read_bytes()
    destination = tmp_path / ("existing" + source.suffix)
    destination.write_bytes(b"Keep destination")
    with pytest.raises(RemediationError, match="unselected or unestablished content"):
        remediate(source, destination, [NormalizeSpacing("Second reference", ("Base",))])
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"Keep destination"


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
def test_ordinary_heading_consumer_requires_explicit_heading_selection(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path]
) -> None:
    styles = STYLES + (
        '<style:style style:name="One" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="1cm"/></style:style>'
        '<style:style style:name="Two" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="2cm"/></style:style>'
    )
    body = (
        '<office:text><text:p text:style-name="One">First reference</text:p>'
        '<text:p text:style-name="Two">Second reference</text:p>'
        '<text:p text:style-name="Base">Target</text:p>'
        '<text:h text:style-name="Base" text:outline-level="1">Heading</text:h></office:text>'
    )
    source = author(tmp_path, "text", Variant(body=body, automatic_styles=styles))
    first = tmp_path / ("first" + source.suffix)
    assert remediate(
        source, first, [NormalizeSpacing("First reference", ("Base",), include_headings=True)]
    ).changed
    assert validate(OdfDocument.open(first)).count == 0
    original = first.read_bytes()
    destination = tmp_path / ("existing" + source.suffix)
    destination.write_bytes(b"Keep destination")
    with pytest.raises(RemediationError, match="unselected or unestablished content"):
        remediate(first, destination, [NormalizeSpacing("Second reference", ("Base",))])
    assert first.read_bytes() == original
    assert destination.read_bytes() == b"Keep destination"
    operation = NormalizeSpacing("Second reference", ("Base",), include_headings=True)
    assert remediate(first, destination, [operation]).changed
    document = OdfDocument.open(destination)
    style = select_elements(
        document.tree(Part.CONTENT),
        "//style:style[@style:name='" + derived_style_name("Base") + "']",
    )[0]
    properties = style.find(qn("style", "paragraph-properties"))
    assert properties is not None
    assert properties.get(qn("fo", "margin-top")) == "2cm"
    assert not remediate(destination, tmp_path / ("again" + source.suffix), [operation]).changed
