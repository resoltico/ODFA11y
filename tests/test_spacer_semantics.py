# SPDX-License-Identifier: MPL-2.0
"""Empty text does not make identities, references or metadata removable."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Outcome, Status
from odfa11y.families.text import RemoveEmptySpacers
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .documents import Variant, make_flat, make_package
from .operation_execution import assert_refused, execute_operations

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

PARAGRAPHS = [
    '<text:p xml:id="anchor"/>',
    (
        '<text:p xmlns:xhtml="http://www.w3.org/1999/xhtml" '
        'xhtml:about="#anchor" xhtml:property="dc:title" xhtml:content="Meaning"/>'
    ),
    '<text:p><text:span xmlns:custom="urn:example:authored" custom:ref="anchor"/></text:p>',
    '<text:p><text:s xmlns:custom="urn:example:authored" custom:ref="anchor"/></text:p>',
    '<text:p text:cond-style-name="Conditional"/>',
    "<text:p><!--Authored reference context--></text:p>",
    "<text:p><?authored anchor?></text:p>",
]


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
@pytest.mark.parametrize(
    "paragraph",
    PARAGRAPHS,
    ids=["identity", "rdf", "span", "space", "condition", "comment", "instruction"],
)
def test_empty_semantic_paragraph_is_preserved(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path], paragraph: str
) -> None:
    source = author(tmp_path, "text", Variant(body=f"<office:text>{paragraph}</office:text>"))
    before = source.read_bytes()
    destination = tmp_path / ("result" + source.suffix)
    result = execute_operations(source, destination, [RemoveEmptySpacers()])
    assert not result.changed
    assert source.read_bytes() == before
    original = select_elements(OdfDocument.open(source).tree(Part.CONTENT), "//text:p")[0]
    retained = select_elements(OdfDocument.open(destination).tree(Part.CONTENT), "//text:p")[0]
    assert etree.tostring(retained) == etree.tostring(original)


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
def test_linked_identity_survives_removal_of_inert_spacer(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path]
) -> None:
    body = (
        '<office:text><text:p xml:id="anchor"/><text:p><text:span><text:s text:c="2"/>'
        '</text:span></text:p><text:p><text:a xlink:href="#anchor" xlink:type="simple">'
        "Go to anchor</text:a></text:p></office:text>"
    )
    source = author(tmp_path, "text", Variant(body=body))
    original = source.read_bytes()
    assert validate(OdfDocument.open(source)).count == 0
    destination = tmp_path / ("result" + source.suffix)
    result = execute_operations(source, destination, [RemoveEmptySpacers()])
    assert result.changed
    assert source.read_bytes() == original
    document = OdfDocument.open(destination)
    assert validate(document).count == 0
    tree = document.tree(Part.CONTENT)
    assert len(select_elements(tree, "//*[@xml:id='anchor']")) == 1
    assert len(select_elements(tree, "//text:p")) == 2
    assert select_elements(tree, "//text:a")[0].get(qn("xlink", "href")) == "#anchor"
    assert not execute_operations(
        destination, tmp_path / ("again" + source.suffix), [RemoveEmptySpacers()]
    ).changed


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
def test_spacer_guard_rejects_identity_loss_before_publication(
    tmp_path: Path, author: Callable[[Path, str, Variant], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = author(
        tmp_path,
        "text",
        Variant(
            body='<office:text><text:p xml:id="anchor"/>'
            '<text:p><text:a xlink:href="#anchor" xlink:type="simple">Go</text:a>'
            "</text:p></office:text>"
        ),
    )
    original = source.read_bytes()
    destination = tmp_path / ("existing" + source.suffix)
    destination.write_bytes(b"keep existing destination")

    def damage(_operation: RemoveEmptySpacers, document: OdfDocument) -> tuple[Outcome, ...]:
        tree = document.tree(Part.CONTENT)
        node = select_elements(tree, "//*[@xml:id='anchor']")[0]
        parent = node.getparent()
        assert parent is not None
        parent.remove(node)
        return (Outcome("remove_empty_spacers", Status.APPLIED, "Removed", count=1),)

    monkeypatch.setattr(RemoveEmptySpacers, "apply", damage)
    assert_refused(
        execute_operations(source, destination, [RemoveEmptySpacers()]),
        match="Protected document content changed",
    )
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"keep existing destination"
