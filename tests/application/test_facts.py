# SPDX-License-Identifier: MPL-2.0
"""Facts preserve registered identity and reject incorrect measurement types."""

from typing import cast

import pytest

from odfa11y.errors import InvalidOption
from odfa11y.report import FACT_REGISTRY, FactKey, FactKeys, FactSet


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (FactKeys.PDF_PAGE_COUNT, True),
        (FactKeys.PDF_PAGE_COUNT, 1.0),
        (FactKeys.DOCUMENT_TITLE, 3),
        (FactKeys.PDF_STRUCTURE_TAGS, {"H1": "one"}),
        (FactKeys.FIDELITY_RASTER_CHANGED_RATIOS, ["wrong"]),
    ],
)
def test_fact_type_mismatch_is_rejected(key: FactKey[object], value: object) -> None:
    facts = FactSet()
    with pytest.raises(InvalidOption) as caught:
        facts[key] = value
    assert key.id in str(caught.value)
    assert caught.value.problems
    assert not facts


def test_registered_fact_identity_cannot_be_forged() -> None:
    facts = FactSet({FactKeys.PDF_PAGE_COUNT: 1})
    forged = FactKey[str]("pdf.page_count", str, "Forged definition")
    with pytest.raises(InvalidOption, match="registered"):
        facts[forged] = "wrong"
    with pytest.raises(InvalidOption, match="registered"):
        _ = facts[forged]
    with pytest.raises(InvalidOption, match="registered"):
        facts.get(forged)
    with pytest.raises(InvalidOption, match="registered"):
        facts[cast("FactKey[str]", "pdf.page_count")] = "wrong"
    assert facts[FactKeys.PDF_PAGE_COUNT] == 1
    assert FACT_REGISTRY["pdf.page_count"] is FactKeys.PDF_PAGE_COUNT


def test_facts_preserve_namespaces_nullable_values_and_registered_measurements() -> None:
    facts = FactSet({FactKeys.DOCUMENT_TITLE: "Source", FactKeys.PDF_TITLE: "Export"})
    facts[FactKeys.DOCUMENT_LANGUAGE] = None
    assert facts.get(FactKeys.PDF_PAGE_COUNT) is None
    assert facts.as_dict() == {
        "document.title": "Source",
        "pdf.title": "Export",
        "document.language": None,
    }
