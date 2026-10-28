# SPDX-License-Identifier: MPL-2.0
"""Missing authored graphic text has one acceptance criterion across source families."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .spreadsheet_fixtures import make_spreadsheet, picture, row, sheet

ROOT = Path(__file__).parent
SOURCES = {
    "text": ROOT / "corpus/images-undescribed.odt",
    "presentation": ROOT / "family_corpus/fruit-presentation.odp",
    "drawing": ROOT / "family_corpus/fruit-drawing.odg",
    "image": ROOT / "family_corpus/fruit-image.odi",
}


@pytest.mark.parametrize("family", ["text", "spreadsheet", "presentation", "drawing", "image"])
@pytest.mark.parametrize(
    ("title", "description", "missing"),
    [
        (None, None, True),
        ("Fruit", None, False),
        (None, "Fruit counts", False),
        ("Fruit", "Fruit counts", False),
        (" \t", "\n ", True),
    ],
    ids=["absent", "title-only", "description-only", "both", "blank"],
)
def test_graphic_text_criteria_are_identical_across_families(
    tmp_path: Path, family: str, title: str | None, description: str | None, *, missing: bool
) -> None:
    source = (
        make_spreadsheet(tmp_path, "package", sheet("Fruit", row(picture())))
        if family == "spreadsheet"
        else SOURCES[family]
    )
    document = OdfDocument.open(source)
    baseline = validate(document)
    frames = select_elements(
        document.tree(Part.CONTENT), "//draw:frame[draw:image or draw:object or draw:object-ole]"
    )
    assert frames
    for frame in frames:
        for child in list(frame):
            if child.tag in {qn("svg", "title"), qn("svg", "desc")}:
                frame.remove(child)
        for tag, value in (("title", title), ("desc", description)):
            if value is not None:
                node = etree.Element(qn("svg", tag))
                node.text = value
                frame.append(node)
    candidate = document.save(tmp_path / ("candidate" + source.suffix))
    before = candidate.read_bytes()
    report = audit_odf(candidate)
    assert any(f.rule_id == "GRAPHIC003" for f in report.findings) is missing
    assert candidate.read_bytes() == before
    assert validate(OdfDocument.open(candidate)).count == baseline.count
    report.as_dict()
