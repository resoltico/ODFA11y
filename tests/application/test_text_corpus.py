# SPDX-License-Identifier: MPL-2.0
"""Verify declared Writer fixture bytes, authoring sources, producer and schema baselines."""

from __future__ import annotations

import hashlib
import json

import pytest

from odfa11y.odf import OdfDocument, Part, select_elements, validate
from tests.fixtures.paths import TESTS

ROOT = TESTS / "text_corpus"
MANIFEST = json.loads((ROOT / "manifest.json").read_text())


def test_text_structure_corpus_inventory_is_complete() -> None:
    assert MANIFEST["documents"]
    assert set(MANIFEST["documents"]) == {path.name for path in ROOT.glob("*.odt")}
    assert {path.stem for path in (ROOT / "sources").glob("*.fodt")} == {
        path.stem for path in ROOT.glob("*.odt")
    }


@pytest.mark.parametrize("name", sorted(MANIFEST["documents"]))
def test_text_structure_corpus_identity_and_native_producer(name: str) -> None:
    source = ROOT / name
    expected = MANIFEST["documents"][name]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected["sha256"]
    authoring = ROOT / "sources" / (source.stem + ".fodt")
    assert hashlib.sha256(authoring.read_bytes()).hexdigest() == expected["source_sha256"]
    document = OdfDocument.open(source)
    assert validate(document).count == expected["schema_violations"]
    generator = select_elements(document.tree(Part.META), "./office:meta/meta:generator")
    assert len(generator) == 1
    assert (generator[0].text or "").startswith("LibreOffice/" + MANIFEST["producer"] + "$")
