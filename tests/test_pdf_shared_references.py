# SPDX-License-Identifier: MPL-2.0
"""Incoming ownership edges survive shared PDF containers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf import audit_pdfua, structure_walk

from .pdf_fixtures import dictionary, register, tagged_writer
from .test_pdf_marked_content import leaves


@pytest.mark.parametrize("array", [False, True])
def test_shared_reference_counts_each_owner(tmp_path: Path, *, array: bool) -> None:
    writer = tagged_writer(["H1", "P"])
    shared = register(
        writer,
        DictionaryObject({
            NameObject("/Type"): NameObject("/MCR"),
            NameObject("/MCID"): NumberObject(0),
            NameObject("/Pg"): writer.pages[0].indirect_reference,
        }),
    )
    if array:
        shared = register(writer, ArrayObject([shared]))
    for leaf in leaves(writer):
        dictionary(leaf)[NameObject("/K")] = shared
    path = tmp_path / "shared.pdf"
    writer.write(path)
    finding = next(f for f in audit_pdfua(path).findings if f.rule_id == "PDF022")
    assert finding.details["mcids"][0]["references"] == 2


def test_shared_empty_arrays_hit_traversal_work_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(structure_walk, "MAX_STRUCTURE_NODES", 20)
    value = ArrayObject([])
    for _ in range(5):
        value = ArrayObject([value, value])
    root = DictionaryObject({NameObject("/K"): value})
    with pytest.raises(ToolFailedError, match="more than 20"):
        structure_walk.build_tree(root)
