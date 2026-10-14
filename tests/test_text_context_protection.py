# SPDX-License-Identifier: MPL-2.0
"""Current flow and protected references are independent of displayed word equality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

import pytest
from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.errors import RemediationError
from odfa11y.families.text import LinkifyAddresses, NormalizeSpacing, RemoveEmptySpacers
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.remediation import SetMetadata, SetOdfVersion, remediate

from .documents import Variant, make_flat

if TYPE_CHECKING:
    from pathlib import Path


BODY = """<office:text>
<text:tracked-changes><text:changed-region text:id="revision">
<text:deletion><office:change-info><dc:creator>Invented Author</dc:creator>
<dc:date>2026-10-14T12:00:00</dc:date></office:change-info>
<text:h text:outline-level="9">Deleted heading</text:h><text:p>https://deleted.example</text:p>
</text:deletion></text:changed-region></text:tracked-changes>
<text:h text:outline-level="1">Main heading</text:h>
<text:p>One<text:s/>Two<text:tab/>Three<text:line-break/>Four
<text:a xlink:href="https://original.example" xlink:type="simple">Original label</text:a>
<text:bookmark text:name="retained"/><text:page-number>1</text:page-number>
<text:note text:id="note" text:note-class="footnote"><text:note-citation>1</text:note-citation>
<text:note-body><text:h text:outline-level="8">Note heading</text:h>
<text:p>https://note.example</text:p></text:note-body></text:note>
<office:annotation><dc:creator>Invented Author</dc:creator><dc:date>2026-10-14T12:00:00</dc:date>
<text:p>https://comment.example</text:p></office:annotation>
</text:p><text:section text:name="conditional" text:condition="true" text:display="condition">
<text:p>https://hidden.example</text:p></text:section>
</office:text>"""


@dataclass(frozen=True, slots=True)
class DamageTextFact(Operation):
    """Change a protected XML fact without changing ordinary words."""

    action: str
    name: ClassVar[str] = "damage_text_fact"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        root = document.edit(Part.CONTENT)
        if self.action == "href":
            select_elements(root, "//text:a")[0].set(qn("xlink", "href"), "https://changed.example")
        elif self.action == "separator":
            node = select_elements(root, "//text:s")[0]
            parent = node.getparent()
            assert parent is not None
            parent.remove(node)
        elif self.action == "bookmark":
            select_elements(root, "//text:bookmark")[0].set(qn("text", "name"), "changed")
        elif self.action == "field":
            select_elements(root, "//text:page-number")[0].set(
                qn("text", "select-page"), "previous"
            )
        elif self.action == "frame_position":
            select_elements(root, "//draw:frame")[0].set(qn("svg", "x"), "2cm")
        elif self.action == "frame_resource":
            select_elements(root, "//draw:image")[0].set(
                qn("xlink", "href"), "Pictures/changed.png"
            )
        elif self.action == "annotation":
            select_elements(root, "//office:annotation//dc:creator")[0].text = "Changed Author"
        elif self.action == "style":
            select_elements(root, "//text:p")[0].set(qn("text", "style-name"), "Changed")
        return (Outcome(self.name, Status.APPLIED, "Changed a fact", count=1),)


@pytest.mark.parametrize(
    "action",
    [
        "href",
        "separator",
        "bookmark",
        "field",
        "annotation",
        "style",
        "frame_position",
        "frame_resource",
    ],
)
def test_same_words_do_not_allow_protected_damage(tmp_path: Path, action: str) -> None:
    start = BODY.index("<text:tracked-changes>")
    end = BODY.index("</text:tracked-changes>") + len("</text:tracked-changes>")
    body = (BODY[:start] + BODY[end:]).replace(
        "</office:text>",
        '<text:p><draw:frame draw:name="Artwork" svg:x="1cm" svg:width="1cm" svg:height="1cm">'
        '<draw:image xlink:href="Pictures/original.png" xlink:type="simple"/>'
        "</draw:frame></text:p></office:text>",
    )
    source = make_flat(tmp_path, "text", Variant(body=body))
    original = source.read_bytes()
    destination = tmp_path / "existing.fodt"
    destination.write_bytes(b"keep")
    with pytest.raises(RemediationError, match="Protected document content changed"):
        remediate(source, destination, [DamageTextFact(action)])
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"keep"


@pytest.mark.parametrize(
    "operation",
    [
        LinkifyAddresses(),
        NormalizeSpacing("One", ("Body",)),
        RemoveEmptySpacers(),
        SetOdfVersion("1.4"),
        SetMetadata(language="en-GB"),
    ],
)
def test_revision_edit_refuses_before_first_metadata_edit(
    tmp_path: Path, operation: Operation
) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY))
    original = source.read_bytes()
    with pytest.raises(RemediationError, match="Tracked revisions"):
        remediate(source, tmp_path / "out.fodt", [SetMetadata(title="Allowed alone"), operation])
    assert source.read_bytes() == original
    assert not (tmp_path / "out.fodt").exists()


def test_revision_audit_outline_and_metadata_only_edit(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY))
    report = audit_odf(source)
    assert report.metadata["heading_count"] == 1
    assert {"TXT060", "TXT061"} <= {f.rule_id for f in report.findings}
    plain = [f.details["text"] for f in report.findings if f.rule_id == "TXT030"]
    assert plain == ["https://note.example"]
    destination = tmp_path / "out.fodt"
    result = remediate(source, destination, [SetMetadata(title="Reviewed title")])
    assert result.changed
    before = OdfDocument.open(source).tree(Part.CONTENT)
    after = OdfDocument.open(destination).tree(Part.CONTENT)
    for path in ("//text:tracked-changes", "//office:annotation", "//text:note", "//text:section"):
        assert etree.tostring(select_elements(before, path)[0]) == etree.tostring(
            select_elements(after, path)[0]
        )


def test_linkification_never_enters_stored_or_hidden_contexts(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY))
    document = OdfDocument.open(source)
    LinkifyAddresses().apply(document)  # raw editing remains caller-owned
    tree = document.tree(Part.CONTENT)
    assert len(select_elements(tree, "//text:note//text:a")) == 1
    assert not select_elements(
        tree,
        "//text:tracked-changes//text:a | //office:annotation//text:a | //text:section//text:a",
    )


def test_inline_hidden_content_and_fields_never_enter_address_prose(tmp_path: Path) -> None:
    body = """<office:text><text:p>Visible
<text:hidden-text text:condition="true" text:is-hidden="true">https://hidden.example</text:hidden-text>
<text:conditional-text text:condition="true" text:string-value-if-true="hidden" text:string-value-if-false="hidden">https://conditional.example</text:conditional-text>
<text:variable-get text:name="field">https://field.example</text:variable-get>
<text:span>https://visible.example</text:span></text:p></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    report = audit_odf(source)
    assert [f.details["text"] for f in report.findings if f.rule_id == "TXT030"] == [
        "https://visible.example"
    ]
    destination = tmp_path / "out.fodt"
    remediate(source, destination, [LinkifyAddresses()])
    after = OdfDocument.open(destination).tree(Part.CONTENT)
    assert len(select_elements(after, "//text:a")) == 1
    assert not select_elements(
        after,
        (
            "//text:hidden-text//text:a | //text:conditional-text//text:a | "
            "//text:variable-get//text:a"
        ),
    )


def test_foreign_authored_payload_is_not_current_flow(tmp_path: Path) -> None:
    body = """<office:text><text:p>Current https://current.example</text:p>
<custom:payload xmlns:custom="urn:example:authored"><text:p>https://foreign.example</text:p></custom:payload>
</office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    destination = tmp_path / "out.fodt"
    report = audit_odf(source)
    assert [f.details["text"] for f in report.findings if f.rule_id == "TXT030"] == [
        "https://current.example"
    ]
    remediate(source, destination, [LinkifyAddresses()])
    before = OdfDocument.open(source).tree(Part.CONTENT)
    after = OdfDocument.open(destination).tree(Part.CONTENT)
    payload = "{urn:example:authored}payload"
    assert etree.tostring(next(before.iter(payload))) == etree.tostring(next(after.iter(payload)))
