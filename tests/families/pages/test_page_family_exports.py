# SPDX-License-Identifier: MPL-2.0
"""Real current Impress/Draw documents prove source repair and complete PDF assurance."""

import hashlib
import tomllib
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
from tests.fixtures.operations import apply_answers
from tests.fixtures.paths import TESTS
lazy from tests.fixtures.answers import graphic_inputs, page_inputs

CORPUS = TESTS / "family_corpus"
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
    manifest = tomllib.loads((CORPUS / "manifest.toml").read_text())
    assert manifest["producer"] == "LibreOffice 26.8.0.3"
    expected = {f"fruit-{family}{suffix}" for family, (suffix, _) in FAMILIES.items()}
    assert {
        entry["file"] for entry in manifest["documents"] if entry["family"] in FAMILIES
    } == expected
    for entry in manifest["documents"]:
        source = CORPUS / entry["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
        result = validate(OdfDocument.open(source))
        assert result.version == manifest["odf_version"] == "1.4"
        assert result.count == entry["schema_violations"] == 0


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
