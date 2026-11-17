# SPDX-License-Identifier: AGPL-3.0-only
"""Negative controls challenge normalization for actual supported operations."""

from collections.abc import Sequence
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.families.text.kinds import LINKIFY_ADDRESSES, TABLE_HEADERS
from odfa11y.odf import Part, qn, select_elements
from odfa11y.remediate.document_ops import COMMON_KINDS
from tests.families.text.test_text_context_protection import BODY
from tests.fixtures.answers import (
    Authored,
    address_input,
    fault_input,
    header_answer,
    header_inputs,
    metadata_input,
)
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import apply_answers, assert_refused
lazy from odfa11y.decisions import Decision
lazy from odfa11y.decisions.edit import EditResult
lazy from odfa11y.odf import OdfDocument


def test_new_exact_address_wrapper_inside_field_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = """<office:text><text:p>https://visible.example
<text:page-number>https://field.example</text:page-number></text:p></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    original_apply = LINKIFY_ADDRESSES.edit

    def corrupt(document: OdfDocument, operation: Decision) -> EditResult:
        outcomes = original_apply(document, operation)
        field = select_elements(document.tree(Part.CONTENT), "//text:page-number")[0]
        link = etree.SubElement(field, qn("text", "a"))
        link.set(qn("xlink", "type"), "simple")
        assert field.text is not None
        link.set(qn("xlink", "href"), field.text)
        link.text, field.text = field.text, None
        return outcomes

    _refuses(source, tmp_path / "output.fodt", [fault_input(address_input(), corrupt)])


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
    original_apply = COMMON_KINDS[1].edit

    def corrupt(document: OdfDocument, operation: Decision) -> EditResult:
        outcomes = original_apply(document, operation)
        tree = document.tree(Part.CONTENT)
        node = (
            next(tree.iter("{urn:example:authored}title"))
            if expression == "//foreign:title"
            else select_elements(tree, expression)[0]
        )
        node.text = "Changed protected fact"
        return outcomes

    _refuses(
        source,
        tmp_path / "output.fodt",
        [fault_input(metadata_input(title="Reviewed title"), corrupt)],
    )


def test_selected_outer_table_cannot_mask_unselected_nested_header_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = """<office:text><table:table table:name="Outer"><table:table-column/><table:table-row>
<table:table-cell><text:p>Outer header</text:p><table:table table:name="Inner"><table:table-column/>
<table:table-row><table:table-cell><text:p>Inner value</text:p></table:table-cell></table:table-row>
</table:table></table:table-cell></table:table-row><table:table-row>
<table:table-cell office:value-type="float" office:value="2"><text:p>2</text:p>
</table:table-cell></table:table-row>
</table:table></office:text>"""
    source = make_flat(tmp_path, "text", Variant(body=body))
    original_apply = TABLE_HEADERS.edit

    def corrupt(document: OdfDocument, operation: Decision) -> EditResult:
        outcomes = original_apply(document, operation)
        inner = select_elements(document.tree(Part.CONTENT), "//table:table[@table:name='Inner']")[
            0
        ]
        row = inner.find(qn("table", "table-row"))
        assert row is not None
        headers = etree.Element(qn("table", "table-header-rows"))
        inner.insert(0, headers)
        headers.append(row)
        return outcomes

    _refuses(
        source,
        tmp_path / "output.fodt",
        [fault_input(header_inputs({"Outer": header_answer(rows=1)}), corrupt)],
    )


def _refuses(source: Path, destination: Path, operations: Sequence[Authored]) -> None:
    before = source.read_bytes()
    destination.write_bytes(b"existing destination")
    assert_refused(
        apply_answers(source, destination, operations),
        match="Protected document content changed",
    )
    assert source.read_bytes() == before
    assert destination.read_bytes() == b"existing destination"
