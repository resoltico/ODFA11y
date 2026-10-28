# SPDX-License-Identifier: MPL-2.0
"""Negative controls challenge normalization for actual supported operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.families.text import LinkifyAddresses, MarkTableHeaders, TableHeaders
from odfa11y.odf import Part, qn, select_elements
from odfa11y.remediation import SetMetadata
from tests.families.text.test_text_context_protection import BODY
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import assert_refused, execute_operations

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from odfa11y.adapter import Operation, Outcome
    from odfa11y.odf import OdfDocument


def test_new_exact_address_wrapper_inside_field_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = """<office:text><text:p>https://visible.example
<text:page-number>https://field.example</text:page-number></text:p></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    original_apply = LinkifyAddresses.apply

    def corrupt(operation: LinkifyAddresses, document: OdfDocument) -> tuple[Outcome, ...]:
        outcomes = original_apply(operation, document)
        field = select_elements(document.tree(Part.CONTENT), "//text:page-number")[0]
        link = etree.SubElement(field, qn("text", "a"))
        link.set(qn("xlink", "type"), "simple")
        assert field.text is not None
        link.set(qn("xlink", "href"), field.text)
        link.text, field.text = field.text, None
        return outcomes

    monkeypatch.setattr(LinkifyAddresses, "apply", corrupt)
    _refuses(source, tmp_path / "output.fodt", [LinkifyAddresses()])


@pytest.mark.parametrize("expression", ["//text:tracked-changes//dc:creator", "//foreign:title"])
def test_metadata_normalization_does_not_mask_history_or_foreign_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, expression: str
) -> None:
    body = BODY.replace(
        "</office:text>",
        '<foreign:title xmlns:foreign="urn:example:authored">Protected title</foreign:title>'
        "</office:text>",
    )
    source = make_flat(tmp_path, "text", Variant(body=body))
    original_apply = SetMetadata.apply

    def corrupt(operation: SetMetadata, document: OdfDocument) -> tuple[Outcome, ...]:
        outcomes = original_apply(operation, document)
        tree = document.tree(Part.CONTENT)
        node = (
            next(tree.iter("{urn:example:authored}title"))
            if expression == "//foreign:title"
            else select_elements(tree, expression)[0]
        )
        node.text = "Changed protected fact"
        return outcomes

    monkeypatch.setattr(SetMetadata, "apply", corrupt)
    _refuses(source, tmp_path / "output.fodt", [SetMetadata(title="Reviewed title")])


def test_selected_outer_table_cannot_mask_unselected_nested_header_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = """<office:text><table:table table:name="Outer"><table:table-row>
<table:table-cell><text:p>Outer header</text:p><table:table table:name="Inner">
<table:table-row><table:table-cell><text:p>Inner value</text:p></table:table-cell></table:table-row>
</table:table></table:table-cell></table:table-row><table:table-row>
<table:table-cell><text:p>Outer value</text:p></table:table-cell></table:table-row>
</table:table></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    original_apply = MarkTableHeaders.apply

    def corrupt(operation: MarkTableHeaders, document: OdfDocument) -> tuple[Outcome, ...]:
        outcomes = original_apply(operation, document)
        inner = select_elements(document.tree(Part.CONTENT), "//table:table[@table:name='Inner']")[
            0
        ]
        row = inner.find(qn("table", "table-row"))
        assert row is not None
        headers = etree.Element(qn("table", "table-header-rows"))
        inner.insert(0, headers)
        headers.append(row)
        return outcomes

    monkeypatch.setattr(MarkTableHeaders, "apply", corrupt)
    _refuses(source, tmp_path / "output.fodt", [MarkTableHeaders({"Outer": TableHeaders(rows=1)})])


def _refuses(source: Path, destination: Path, operations: Sequence[Operation]) -> None:
    before = source.read_bytes()
    destination.write_bytes(b"existing destination")
    assert_refused(
        execute_operations(source, destination, operations),
        match="Protected document content changed",
    )
    assert source.read_bytes() == before
    assert destination.read_bytes() == b"existing destination"
