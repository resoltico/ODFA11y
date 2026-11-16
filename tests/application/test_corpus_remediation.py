# SPDX-License-Identifier: MPL-2.0
"""Remediating real Writer documents: a plan is idempotent and never harms text or schema."""

lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.odf import OdfDocument, Part, validate
from tests.fixtures.answers import (
    Authored,
    address_input,
    graphic_answer,
    graphic_inputs,
    metadata_input,
    spacer_input,
)
from tests.fixtures.corpus import DOCUMENT_IDS, DOCUMENTS, visible_text
from tests.fixtures.operations import apply_answers
lazy from tests.fixtures.corpus import CorpusDocument

# Writer names the first picture and the first table of these documents "Image1" and "Table1".
PLAN_EXTRAS: dict[str, Authored] = {
    "images-undescribed": graphic_inputs({"Image1": graphic_answer("Red square")}),
}


def _plan(document: CorpusDocument) -> list[Authored]:
    operations: list[Authored] = [
        metadata_input(title="Corpus document", language="en-US"),
        address_input(),
        spacer_input(),
    ]
    if document.stem in PLAN_EXTRAS:
        operations.append(PLAN_EXTRAS[document.stem])
    return operations


def _parts(path: Path) -> list[bytes]:
    opened = OdfDocument.open(path)
    return [etree.tostring(opened.tree(part)) for part in (Part.CONTENT, Part.STYLES, Part.META)]


@pytest.mark.parametrize("document", DOCUMENTS, ids=DOCUMENT_IDS)
def test_a_plan_is_idempotent_and_keeps_text_and_schema_validity(
    document: CorpusDocument, tmp_path: Path
) -> None:
    suffix = document.path.suffix
    once, twice = tmp_path / f"once{suffix}", tmp_path / f"twice{suffix}"
    first = apply_answers(document.path, once, _plan(document))
    assert first.changed
    assert first.schema.status == "passed"
    assert first.schema.new_count == 0
    assert visible_text(once) == visible_text(document.path)
    second = apply_answers(once, twice, _plan(document))
    assert not second.changed
    assert _parts(twice) == _parts(once)
    assert validate(OdfDocument.open(twice)).count <= document.schema_violations


@pytest.mark.parametrize("document", DOCUMENTS, ids=DOCUMENT_IDS)
def test_a_plan_leaves_exactly_the_findings_it_cannot_resolve(
    document: CorpusDocument, tmp_path: Path
) -> None:
    result = tmp_path / f"result{document.path.suffix}"
    apply_answers(document.path, result, _plan(document))
    assert {finding.rule_id for finding in audit_odf(result).findings} == document.rules_after_plan
