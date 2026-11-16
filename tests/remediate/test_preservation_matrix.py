# SPDX-License-Identifier: AGPL-3.0-only
"""Replay the old proof's fixed edit intents against the recorded corpus bytes."""

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from lxml import etree

from odfa11y.application.remediate import remediate
from odfa11y.decisions import DecisionScope
from odfa11y.odf import OdfDocument, Part, qn, regressions, select_elements, validate
from odfa11y.remediate.catalogue import registered_kinds
from tests.fixtures.paths import REPOSITORY
from tests.fixtures.preservation import answer_values, materialize, observation, target_bindings

MATRIX = json.loads((REPOSITORY / "tests/corpus/preservation.json").read_text())
CASES = MATRIX["cases"]
# FAM-002 corrects these historical schema-only refusals. The capture stays immutable;
# current acceptance additionally proves that only the reviewed title attributes changed.
SCHEMA_METADATA_REPAIRS = frozenset({
    "tests/corpus/structure/sources/references-negative.fodt",
    "tests/corpus/structure/sources/references-positive.fodt",
})


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["source"] + "::" + case["kind"])
def test_preservation_characterisation(case: dict[str, object], tmp_path: Path) -> None:
    source = REPOSITORY / str(case["source"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == case["sha256"]
    kind = registered_kinds()[str(case["kind"])]
    if case["expected"] == "no-targets":
        document = OdfDocument.open(source)
        if kind.scope is DecisionScope.TARGET:
            assert list(target_bindings(document, kind)) == []
        else:
            assert answer_values(document, kind, None, 1) == {}
        return
    if kind.id == "link.description" and case["source"] in SCHEMA_METADATA_REPAIRS:
        assert case["expected"] == "refused"
        _assert_schema_metadata_repair(source, tmp_path / source.name, case)
        return
    assert (
        observation(
            source,
            kind,
            cast(list[dict[str, object]], case["answers"]),
            tmp_path / ("candidate" + source.suffix),
        )
        == case["expected"]
    )


def _assert_schema_metadata_repair(source: Path, destination: Path, case) -> None:
    kind = registered_kinds()["link.description"]
    result = remediate(source, destination, materialize(source, kind, case["answers"]))
    assert result.published
    assert result.schema.before_count == result.schema.after_count == 1
    assert result.schema.new_count == 0
    original, candidate = OdfDocument.open(source), OdfDocument.open(destination)
    old, new = validate(original), validate(candidate)
    assert old.messages() == new.messages()
    assert regressions(old, new)  # Independent snapshots still reproduce the old fingerprint delta.
    before = select_elements(original.tree(Part.CONTENT), "//text:a | //draw:a")
    after = select_elements(candidate.tree(Part.CONTENT), "//text:a | //draw:a")
    assert len(before) == len(after) == len(case["answers"])
    for left, right in zip(before, after, strict=True):
        assert right.get(qn("office", "title")) == "Reviewed destination"
        previous = left.get(qn("office", "title"))
        if previous is None:
            right.attrib.pop(qn("office", "title"))
        else:
            right.set(qn("office", "title"), previous)
    assert etree.tostring(
        original.tree(Part.CONTENT), method="c14n", exclusive=True, with_comments=True
    ) == etree.tostring(
        candidate.tree(Part.CONTENT), method="c14n", exclusive=True, with_comments=True
    )
