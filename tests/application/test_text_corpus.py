# SPDX-License-Identifier: MPL-2.0
"""Stored Writer structure and authoring bytes share the unified corpus authority."""

import hashlib

import pytest

from odfa11y.odf import OdfDocument, Part, select_elements, validate
from tests.fixtures.corpus import ALL_DOCUMENTS, CORPUS

DOCUMENTS = tuple(item for item in ALL_DOCUMENTS if "text-structure" in item.purposes)
BY_FILE = {item.file: item for item in ALL_DOCUMENTS}


def test_text_structure_corpus_inventory_is_complete() -> None:
    assert DOCUMENTS
    assert {item.path for item in DOCUMENTS} == set((CORPUS / "structure").glob("*.odt"))
    assert {item.path.stem for item in DOCUMENTS} == {
        path.stem for path in (CORPUS / "structure/sources").glob("*.fodt")
    }


@pytest.mark.parametrize("expected", DOCUMENTS, ids=lambda item: item.file)
def test_text_structure_corpus_identity_and_native_producer(expected) -> None:
    assert hashlib.sha256(expected.path.read_bytes()).hexdigest() == expected.sha256
    assert expected.source is not None
    source = BY_FILE[expected.source]
    assert hashlib.sha256(source.path.read_bytes()).hexdigest() == source.sha256
    document = OdfDocument.open(expected.path)
    assert validate(document).count == expected.schema_violations
    generator = select_elements(document.tree(Part.META), "./office:meta/meta:generator")
    assert len(generator) == 1
    assert (generator[0].text or "").startswith(
        "LibreOffice/" + expected.producer.removeprefix("LibreOffice ") + "$"
    )
