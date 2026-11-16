# SPDX-License-Identifier: MPL-2.0
"""Annotation absence is established separately from unreadable annotation data."""

import pytest
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NullObject, NumberObject

from odfa11y import audit
from odfa11y.pdf.reading import open_pdf
from odfa11y.pdf.structure.links import link_annotations
from odfa11y.rules import registry as rules
from tests.fixtures.pdf import tagged_writer


@pytest.mark.parametrize(
    "value",
    [
        None,
        NullObject(),
        ArrayObject(),
        ArrayObject([DictionaryObject({NameObject("/Subtype"): NameObject("/Text")})]),
    ],
    ids=["absent", "null", "empty", "non-link"],
)
def test_established_absence_of_links_is_empty(tmp_path, value) -> None:
    writer = tagged_writer()
    if value is not None:
        writer.pages[0][NameObject("/Annots")] = value
    source = tmp_path / "annotations.pdf"
    writer.write(source)
    with open_pdf(source) as reader:
        assert link_annotations(reader) == []


@pytest.mark.parametrize(
    "value",
    [
        NumberObject(7),
        ArrayObject([NumberObject(7)]),
        ArrayObject([NullObject()]),
        ArrayObject([DictionaryObject({NameObject("/Subtype"): NumberObject(7)})]),
    ],
    ids=["collection", "entry", "null-entry", "subtype"],
)
def test_malformed_annotation_data_is_not_an_empty_measurement(tmp_path, value) -> None:
    writer = tagged_writer()
    writer.pages[0][NameObject("/Annots")] = value
    source = tmp_path / "malformed.pdf"
    writer.write(source)
    with open_pdf(source) as reader, pytest.raises(PdfReadError, match="annotation"):
        link_annotations(reader)


def test_public_audit_marks_unreadable_annotations_as_incomplete(tmp_path) -> None:
    writer = tagged_writer()
    writer.pages[0][NameObject("/Annots")] = NumberObject(7)
    source = tmp_path / "malformed.pdf"
    writer.write(source)
    result = audit(source)
    assert result.exit_status == 2
    assert rules.PDF001.id in {finding.rule_id for finding in result.reports[0].findings}
