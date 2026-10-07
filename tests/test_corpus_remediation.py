# SPDX-License-Identifier: MPL-2.0
"""Remediating real Writer documents: a plan is idempotent and never harms text or schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.families.text import (
    AltText,
    HeaderRows,
    LinkifyAddresses,
    MarkHeaderRows,
    RemoveEmptySpacers,
    SetAltText,
)
from odfa11y.odf import OdfDocument, Part, validate
from odfa11y.remediation import SetMetadata, remediate

from .corpus_manifest import DOCUMENT_IDS, DOCUMENTS, visible_text

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.adapter import Operation

    from .corpus_manifest import CorpusDocument

# Writer names the first picture and the first table of these documents "Image1" and "Table1".
PLAN_EXTRAS: dict[str, Operation] = {
    "images-undescribed": SetAltText({"Image1": AltText("Red square")}),
    "table-no-header-row": MarkHeaderRows({"Table1": HeaderRows(1)}),
}


def _plan(document: CorpusDocument) -> list[Operation]:
    operations: list[Operation] = [
        SetMetadata(title="Corpus document", language="en-US"),
        LinkifyAddresses(),
        RemoveEmptySpacers(),
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
    first = remediate(document.path, once, _plan(document))
    assert first.changed
    assert "no new violations" in first.schema_check
    assert visible_text(once) == visible_text(document.path)
    second = remediate(once, twice, _plan(document))
    assert not second.changed
    assert _parts(twice) == _parts(once)
    assert validate(OdfDocument.open(twice)).count <= document.schema_violations


@pytest.mark.parametrize("document", DOCUMENTS, ids=DOCUMENT_IDS)
def test_a_plan_leaves_exactly_the_findings_it_cannot_resolve(
    document: CorpusDocument, tmp_path: Path
) -> None:
    result = tmp_path / f"result{document.path.suffix}"
    remediate(document.path, result, _plan(document))
    assert {finding.rule_id for finding in audit_odf(result).findings} == document.rules_after_plan
