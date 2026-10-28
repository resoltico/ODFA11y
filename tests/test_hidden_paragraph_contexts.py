# SPDX-License-Identifier: MPL-2.0
"""A hidden-paragraph condition excludes its whole block, regardless of cached visibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf, prepare_plan
from odfa11y.content import GraphicAlternative, document_links, eligible_text_node
from odfa11y.families.text import LinkifyAddresses, SetGraphicAlternatives
from odfa11y.odf import OdfDocument, Part, select_elements, validate
from odfa11y.report import FactKeys

from .documents import Variant, make_flat, make_package
from .operation_execution import execute_operations

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("layout", ["package", "flat"])
@pytest.mark.parametrize("hidden", ["true", "false"])
@pytest.mark.parametrize("block", ["p", "h"])
def test_conditional_paragraph_block_and_descendants_remain_unedited(
    tmp_path: Path, layout: str, hidden: str, block: str
) -> None:
    level = ' text:outline-level="7"' if block == "h" else ""
    body = f"""<office:text><text:{block}{level}>
<text:hidden-paragraph text:condition="true" text:is-hidden="{hidden}"/>
Conditional heading https://hidden.example
<text:a xlink:type="simple" xlink:href="https://hidden-link.example"/>
<draw:frame draw:name="ConditionalBox" text:anchor-type="as-char" svg:width="1cm" svg:height="1cm">
<draw:text-box><table:table table:name="ConditionalTable"><table:table-column/>
<table:table-row><table:table-cell><text:p>https://hidden-cell.example</text:p></table:table-cell>
</table:table-row></table:table></draw:text-box></draw:frame>
</text:{block}><text:h text:outline-level="3">Visible heading</text:h>
<text:p>Visible paragraph https://visible.example
<text:a xlink:type="simple" xlink:href="https://visible-link.example"/></text:p></office:text>"""
    maker = make_package if layout == "package" else make_flat
    source = maker(tmp_path, "text", Variant(body=body))
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    excluded = select_elements(document.tree(Part.CONTENT), "//text:hidden-paragraph/..")[0]
    before = etree.tostring(excluded)
    assert all(not eligible_text_node(node) for node in excluded.iter())
    report, template = prepare_plan(source)
    assert report.facts[FactKeys.TEXT_HEADING_COUNT] == 1
    assert report.facts[FactKeys.TEXT_TABLE_COUNT] == 0
    assert "TXT061" in {finding.rule_id for finding in report.findings}
    addresses = [
        finding.details["text"] for finding in report.findings if finding.rule_id == "TXT030"
    ]
    assert addresses == ["https://visible.example"]
    assert len(document_links(document)) == 1
    assert template is not None
    assert "content/heading[1]" in template
    assert 'decisions."link.description"."content/link[1]"' in template
    assert "ConditionalBox" not in template
    assert "ConditionalTable" not in template
    assert (
        SetGraphicAlternatives({"ConditionalBox": GraphicAlternative(title="Reviewed")})
        .apply(document)[0]
        .status
        is Status.FAILED
    )
    assert etree.tostring(excluded) == before
    result = LinkifyAddresses().apply(document)
    assert result[0].count == 1
    assert etree.tostring(excluded) == before
    destination = tmp_path / ("out.odt" if layout == "package" else "out.fodt")
    assert execute_operations(source, destination, [LinkifyAddresses()]).changed
    reloaded = OdfDocument.open(destination)
    retained = select_elements(reloaded.tree(Part.CONTENT), "//text:hidden-paragraph/..")[0]
    assert etree.tostring(retained) == before
    after = audit_odf(destination)
    assert after.facts[FactKeys.TEXT_HEADING_COUNT] == 1
    assert "TXT061" in {finding.rule_id for finding in after.findings}


@pytest.mark.parametrize("layout", ["package", "flat"])
@pytest.mark.parametrize("hidden", ["true", "false"])
def test_span_marker_excludes_its_whole_paragraph_including_sibling_prose(
    tmp_path: Path, layout: str, hidden: str
) -> None:
    body = '<office:text><text:p><text:span><text:hidden-paragraph text:condition="true" '
    body += f'text:is-hidden="{hidden}"/>https://span.example</text:span> '
    body += "https://sibling.example</text:p><text:p>https://visible.example</text:p></office:text>"
    source = (make_package if layout == "package" else make_flat)(
        tmp_path, "text", Variant(body=body)
    )
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    report = audit_odf(source)
    assert "TXT061" in {finding.rule_id for finding in report.findings}
    assert [
        finding.details["text"] for finding in report.findings if finding.rule_id == "TXT030"
    ] == ["https://visible.example"]
    conditional = select_elements(
        document.tree(Part.CONTENT), "//text:hidden-paragraph/ancestor::text:p"
    )[0]
    before = etree.tostring(conditional)
    assert LinkifyAddresses().apply(document)[0].count == 1
    assert etree.tostring(conditional) == before


def test_note_marker_does_not_hide_unrelated_enclosing_paragraph(tmp_path: Path) -> None:
    body = (
        "<office:text><text:p>https://outer.example"
        '<text:note text:id="n" text:note-class="footnote">'
        "<text:note-citation>1</text:note-citation><text:note-body><text:p>"
        '<text:hidden-paragraph text:condition="true" text:is-hidden="false"/>https://note.example'
        "</text:p></text:note-body></text:note></text:p></office:text>"
    )
    document = OdfDocument.open(make_flat(tmp_path, "text", Variant(body=body)))
    assert validate(document).count == 0
    outer = select_elements(document.tree(Part.CONTENT), "//office:text/text:p")[0]
    inner = select_elements(document.tree(Part.CONTENT), "//text:note-body/text:p")[0]
    assert eligible_text_node(outer)
    assert not eligible_text_node(inner)
    before = etree.tostring(inner)
    assert LinkifyAddresses().apply(document)[0].count == 1
    assert etree.tostring(inner) == before
