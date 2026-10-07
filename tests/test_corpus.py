# SPDX-License-Identifier: MPL-2.0
"""The Writer corpus: stored bytes, audit findings and schema validity of real documents."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.odf import OdfDocument, Part, select_elements, validate

from .corpus_manifest import (
    CORPUS,
    DOCUMENT_IDS,
    DOCUMENT_SUFFIXES,
    DOCUMENTS,
    visible_text,
)

if TYPE_CHECKING:
    from .corpus_manifest import CorpusDocument

EVERY_DOCUMENT = pytest.mark.parametrize("document", DOCUMENTS, ids=DOCUMENT_IDS)
CORPUS_RULES = {"TXT002", "TXT005", "TXT010", "TXT020", "TXT021", "TXT030", "TXT040"}


def _findings(document: CorpusDocument) -> set[str]:
    return {finding.rule_id for finding in audit_odf(document.path).findings}


def test_the_manifest_lists_exactly_the_documents_in_the_corpus() -> None:
    stored = {path.name for path in CORPUS.iterdir() if path.suffix in DOCUMENT_SUFFIXES}
    assert stored == set(DOCUMENT_IDS)
    assert len(DOCUMENT_IDS) == len(set(DOCUMENT_IDS))


def test_the_readme_describes_every_document() -> None:
    readme = (CORPUS / "README.md").read_text(encoding="utf-8")
    assert [name for name in DOCUMENT_IDS if f"`{name}`" not in readme] == []


@EVERY_DOCUMENT
def test_a_document_keeps_the_bytes_the_manifest_records(document: CorpusDocument) -> None:
    assert hashlib.sha256(document.path.read_bytes()).hexdigest() == document.sha256


@EVERY_DOCUMENT
def test_a_document_audits_to_exactly_its_expected_rules(document: CorpusDocument) -> None:
    assert _findings(document) == document.rules


@EVERY_DOCUMENT
def test_a_document_has_the_recorded_number_of_schema_violations(
    document: CorpusDocument,
) -> None:
    assert validate(OdfDocument.open(document.path)).count == document.schema_violations


@EVERY_DOCUMENT
def test_a_document_carries_no_tracked_changes(document: CorpusDocument) -> None:
    content = OdfDocument.open(document.path).tree(Part.CONTENT)
    assert select_elements(content, "//text:tracked-changes") == []


def test_the_corpus_covers_every_text_rule_it_claims_and_includes_clean_documents() -> None:
    expected = [rule for document in DOCUMENTS for rule in document.rules]
    assert set(expected) == CORPUS_RULES
    assert any(not document.rules for document in DOCUMENTS)


def test_package_and_flat_forms_of_a_document_are_equivalent() -> None:
    forms: dict[str, list[CorpusDocument]] = defaultdict(list)
    for document in DOCUMENTS:
        forms[document.stem].append(document)
    pairs = [found for found in forms.values() if len(found) == 2]
    assert pairs, "the corpus needs documents stored in both forms"
    for first, second in pairs:
        opened = [OdfDocument.open(each.path) for each in (first, second)]
        assert {document.layout for document in opened} == {"package", "flat"}, first.stem
        reports = [audit_odf(each.path).findings for each in (first, second)]
        assert sorted((f.rule_id, f.message) for f in reports[0]) == sorted(
            (f.rule_id, f.message) for f in reports[1]
        ), first.stem
        assert visible_text(first.path) == visible_text(second.path), first.stem
        # libxml2 stops at the first error of a failing content model, so the counts of the two
        # layouts may differ; whether the document is valid may not.
        verdicts = {validate(each).count == 0 for each in opened}
        assert len(verdicts) == 1, first.stem
