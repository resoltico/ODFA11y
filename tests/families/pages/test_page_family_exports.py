# SPDX-License-Identifier: AGPL-3.0-only
"""Real current Impress/Draw documents prove source repair and complete PDF assurance."""

import hashlib
from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.families import pages
from odfa11y.odf import OdfDocument, validate
from tests.fixtures.answers import (
    Authored,
    graphic_answer,
    metadata_input,
    page_answer,
)
from tests.fixtures.corpus import ALL_DOCUMENTS
from tests.fixtures.operations import apply_answers
from tests.fixtures.paths import TESTS
lazy from tests.fixtures.answers import graphic_inputs, page_inputs

CORPUS = TESTS / "corpus/families"
FAMILIES = {"presentation": (".odp", pages), "drawing": (".odg", pages)}


def _plan() -> list[Authored]:
    return [
        metadata_input(language="en-US"),
        page_inputs({
            "Fruit overview": page_answer(
                "Fruit overview", "Fruit counts and an illustration", ("id2", "id1", "id3")
            )
        }),
        graphic_inputs({
            "Fruit illustration": graphic_answer(
                "Fruit illustration", "A red apple and a green pear"
            )
        }),
    ]


def test_native_family_corpus_matches_provenance_and_validates() -> None:
    documents = tuple(item for item in ALL_DOCUMENTS if "family-conformance" in item.purposes)
    expected = {f"families/fruit-{family}{suffix}" for family, (suffix, _) in FAMILIES.items()}
    assert {item.file for item in documents if item.family in FAMILIES} == expected
    for item in documents:
        assert hashlib.sha256(item.path.read_bytes()).hexdigest() == item.sha256
        result = validate(OdfDocument.open(item.path))
        assert result.version == item.odf_version == "1.4"
        assert result.count == item.schema_violations == 0
        if item.producer.startswith("LibreOffice"):
            assert item.producer == "LibreOffice 26.8.0.3"


@pytest.mark.parametrize("family", FAMILIES)
def test_native_page_plan_removes_its_findings_and_reapplies_unchanged(
    tmp_path: Path, family: str
) -> None:
    suffix, _ = FAMILIES[family]
    source = CORPUS / f"fruit-{family}{suffix}"
    once, twice = tmp_path / f"once{suffix}", tmp_path / f"twice{suffix}"
    assert apply_answers(source, once, _plan()).changed
    assert not apply_answers(once, twice, _plan()).changed
    assert audit_odf(twice, schema=True).findings == []
    assert once.read_bytes() == twice.read_bytes()
