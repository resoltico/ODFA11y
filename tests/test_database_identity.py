# SPDX-License-Identifier: MPL-2.0
"""Declared Base names avoid sibling scans while malformed ordinal targets stay exact."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self, override

from lxml import etree

from odfa11y.families.database.descriptions import targets
from odfa11y.odf import OdfDocument, Part, qn, select_elements

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest

SOURCE = Path(__file__).parent / "family_corpus/fruit-database.odb"


class CountedElement(etree.ElementBase):
    """Count real sibling visits without replacing the XML identity computation."""

    sibling_visits: ClassVar[int] = 0

    @override
    def __iter__(self) -> Iterator[Self]:
        for child in super().__iter__():
            if self.tag == qn("db", "queries"):
                type(self).sibling_visits += 1
            yield child


def _document(monkeypatch: pytest.MonkeyPatch, names: list[str | None]) -> OdfDocument:
    document = OdfDocument.open(SOURCE)
    database = select_elements(document.tree(Part.CONTENT), "//office:database")[0]
    queries = etree.SubElement(database, qn("db", "queries"))
    for name in names:
        attributes = {qn("db", "command"): "SELECT 1"}
        if name is not None:
            attributes[qn("db", "name")] = name
        etree.SubElement(queries, qn("db", "query"), attributes)
    parser = etree.XMLParser()
    parser.set_element_class_lookup(etree.ElementDefaultClassLookup(element=CountedElement))
    counted = etree.ElementTree(
        etree.fromstring(etree.tostring(document.tree(Part.CONTENT)), parser)
    )
    original_tree = document.tree
    monkeypatch.setattr(
        document, "tree", lambda part: counted if part is Part.CONTENT else original_tree(part)
    )
    CountedElement.sibling_visits = 0
    return document


def test_unique_named_queries_never_scan_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _document(monkeypatch, [f"Query {index}" for index in range(1000)])
    actual = targets(document)
    assert len(actual) == 1000
    assert "content/query[name=Query%20999]" in actual
    assert CountedElement.sibling_visits == 0


def test_unnamed_queries_visit_each_sibling_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _document(monkeypatch, [None] * 1000)
    actual = targets(document)
    assert len(actual) == 1000
    assert "content/query[1]" in actual
    assert "content/query[1000]" in actual
    assert CountedElement.sibling_visits == 1000


def test_ordinals_count_named_siblings_and_refresh_after_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(monkeypatch, ["Named", None, "Duplicate", None, "Duplicate"])
    first = targets(document)
    assert "content/query[2]" in first
    assert "content/query[4]" in first
    assert len(first["content/query[name=Duplicate]"]) == 2
    assert CountedElement.sibling_visits == 5
    parent = select_elements(document.tree(Part.CONTENT), "//db:queries")[0]
    parent.insert(
        0,
        etree.Element(
            qn("db", "query"), {qn("db", "name"): "Inserted", qn("db", "command"): "SELECT 2"}
        ),
    )
    CountedElement.sibling_visits = 0
    second = targets(document)
    assert "content/query[3]" in second
    assert "content/query[5]" in second
    assert "content/query[2]" not in second
    assert "content/query[4]" not in second
    assert CountedElement.sibling_visits == 6
