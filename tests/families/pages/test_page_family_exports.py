# SPDX-License-Identifier: MPL-2.0
"""Real current Impress/Draw documents prove source repair and complete PDF assurance."""

import hashlib
import tomllib
lazy from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.concepts import GraphicAlternative, PageDecision
from odfa11y.families import pages
from odfa11y.odf import OdfDocument, validate
from odfa11y.remediate import SetMetadata
from tests.fixtures.operations import execute_operations
from tests.fixtures.paths import TESTS
lazy from odfa11y.concepts.edits import Operation

CORPUS = TESTS / "family_corpus"
FAMILIES = {"presentation": (".odp", pages), "drawing": (".odg", pages)}


def _plan(family: str) -> list[Operation]:
    _, api = FAMILIES[family]
    return [
        SetMetadata(language="en-US"),
        api.SetPageSemantics({
            "Fruit overview": PageDecision(
                "Fruit overview", "Fruit counts and an illustration", ("id2", "id1", "id3")
            )
        }),
        api.SetGraphicAlternatives({
            "Fruit illustration": GraphicAlternative(
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
    assert execute_operations(source, once, _plan(family)).changed
    assert not execute_operations(once, twice, _plan(family)).changed
    assert audit_odf(twice, schema=True).findings == []
    assert once.read_bytes() == twice.read_bytes()
