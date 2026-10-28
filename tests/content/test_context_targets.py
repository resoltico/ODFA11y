# SPDX-License-Identifier: MPL-2.0
"""Review targets compose within established current contexts across both ODF layouts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import GraphicAlternative, LinkDescription, link_fingerprint, link_location
from odfa11y.families.text import (
    LinkifyAddresses,
    MarkTableHeaders,
    SetGraphicAlternatives,
    SetLinkDescriptions,
    TableHeaders,
)
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.source_audit import audit_odf, prepare_plan
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import execute_operations
from tests.fixtures.plans import question_for

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FRAME = (
    '<draw:frame draw:name="Shared"><draw:image xlink:href="Pictures/shared.png" '
    'xlink:type="simple"/></draw:frame>'
)
TABLE = """<table:table table:name="Shared"><table:table-column table:number-columns-repeated="2"/>
<table:table-row><table:table-cell><text:p>Item</text:p></table:table-cell>
<table:table-cell><text:p>Amount</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell><text:p>Apple</text:p></table:table-cell>
<table:table-cell><text:p>3</text:p></table:table-cell></table:table-row></table:table>"""
BODY = (
    "<office:text><text:p>"
    + FRAME
    + """<text:note text:id="note" text:note-class="footnote">
<text:note-citation>1</text:note-citation><text:note-body><text:p>"""
    + FRAME
    + "</text:p>"
    + TABLE
    + "</text:note-body></text:note></text:p>"
    + TABLE
    + "</office:text>"
)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_context_qualified_graphic_and_table_decisions_edit_only_reviewed_note(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    source = make(tmp_path, "text", Variant(body=BODY))
    report, template = prepare_plan(source)
    assert template is not None
    note_graphic = next(
        f
        for f in report.findings
        if f.rule_id == "GRAPHIC003" and f.location and "/note[1]/" in f.location.path
    )
    note_table = next(
        f
        for f in report.findings
        if f.rule_id == "TABLE003" and f.location and "/note[1]/" in f.location.path
    )
    assert note_graphic.location is not None
    assert note_table.location is not None
    assert note_graphic.location.path in template
    assert note_table.location.path in template
    graphic_fingerprint = question_for(report, note_graphic).fingerprint
    table_fingerprint = question_for(report, note_table).fingerprint
    assert isinstance(graphic_fingerprint, str)
    assert isinstance(table_fingerprint, str)
    operations = [
        SetGraphicAlternatives({
            note_graphic.location.path: GraphicAlternative(
                description="The note's illustration",
                fingerprint=graphic_fingerprint,
            )
        }),
        MarkTableHeaders({
            note_table.location.path: TableHeaders(rows=1, fingerprint=table_fingerprint)
        }),
    ]
    output = tmp_path / ("output" + source.suffix)
    assert execute_operations(source, output, operations).changed
    assert not execute_operations(output, tmp_path / ("again" + source.suffix), operations).changed
    tree = OdfDocument.open(output).tree(Part.CONTENT)
    main_frame, note_frame = select_elements(tree, "//draw:frame")
    assert main_frame.find(qn("svg", "desc")) is None
    assert note_frame.findtext(qn("svg", "desc")) == "The note's illustration"
    inner, outer = select_elements(tree, "//table:table")
    assert inner.find(qn("table", "table-header-rows")) is not None
    assert outer.find(qn("table", "table-header-rows")) is None


def test_legal_id_link_plan_composes_with_address_linkification(tmp_path: Path) -> None:
    body = """<office:text><text:p>Visit https://plain.example
<draw:a xml:id="guide" xlink:type="simple" xlink:href="https://guide.example">
<draw:rect draw:name="Guide" svg:width="1cm" svg:height="1cm">
<svg:title>Guide</svg:title></draw:rect>
</draw:a></text:p></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    document = OdfDocument.open(source)
    link = select_elements(document.tree(Part.CONTENT), "//draw:a")[0]
    plan = [
        LinkifyAddresses(),
        SetLinkDescriptions({
            link_location(link, 1).path: LinkDescription(
                "Read the guide", link_fingerprint(document, link)
            )
        }),
    ]
    output = tmp_path / "output.fodt"
    assert execute_operations(source, output, plan).changed
    assert not execute_operations(output, tmp_path / "again.fodt", plan).changed
    report = audit_odf(output)
    assert not any(f.rule_id == "LINK001" for f in report.findings)
    edited = select_elements(OdfDocument.open(output).tree(Part.CONTENT), "//draw:a")[0]
    assert edited.get(qn("office", "title")) == "Read the guide"
    assert edited.get(qn("xlink", "href")) == "https://guide.example"


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_note_targets_ignore_styled_header_notes_in_both_layouts(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    source = make(
        tmp_path,
        "text",
        Variant(
            body="""<office:text><text:p>
<text:note text:id="main-note" text:note-class="footnote"><text:note-citation>1</text:note-citation>
<text:note-body><text:p><text:a xlink:href="https://main.example" xlink:type="simple">Main</text:a>
</text:p></text:note-body></text:note></text:p></office:text>"""
        ),
    )
    document = OdfDocument.open(source)
    root = document.tree(Part.STYLES).getroot()
    master = etree.SubElement(root, qn("office", "master-styles"))
    page = etree.SubElement(master, qn("style", "master-page"), {qn("style", "name"): "Header"})
    header = etree.SubElement(page, qn("style", "header"))
    note = etree.SubElement(header, qn("text", "note"))
    etree.SubElement(note, qn("text", "note-body"))
    link = select_elements(document.tree(Part.CONTENT), "//office:body//text:a")[0]
    assert link_location(link, 1).path == "content/note[1]/link[1]"


def test_unnamed_table_target_requires_reviewed_fingerprint(tmp_path: Path) -> None:
    source = make_flat(
        tmp_path,
        "text",
        Variant(
            body="<office:text>" + TABLE.replace(' table:name="Shared"', "") + "</office:text>"
        ),
    )
    report = audit_odf(source)
    finding = next(f for f in report.findings if f.rule_id == "TABLE003")
    assert finding.location is not None
    document = OdfDocument.open(source)
    operation = MarkTableHeaders({finding.location.path: TableHeaders(rows=1)})
    assert operation.apply(document)[0].status is Status.FAILED
    assert not document.dirty
    reviewed_fingerprint = question_for(report, finding).fingerprint
    assert isinstance(reviewed_fingerprint, str)
    reviewed = MarkTableHeaders({
        finding.location.path: TableHeaders(rows=1, fingerprint=reviewed_fingerprint)
    })
    assert execute_operations(source, tmp_path / "reviewed.fodt", [reviewed]).changed
