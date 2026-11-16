# SPDX-License-Identifier: MPL-2.0
"""Replay the old proof's fixed edit intents against the recorded corpus bytes."""

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from odfa11y.decisions import DecisionScope
from odfa11y.odf import OdfDocument
from odfa11y.remediate.catalogue import registered_kinds
from tests.fixtures.paths import REPOSITORY
from tests.fixtures.preservation import answer_values, observation, target_bindings

MATRIX = json.loads((REPOSITORY / "tests/corpus/preservation.json").read_text())
CASES = MATRIX["cases"]


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
    assert (
        observation(
            source,
            kind,
            cast(list[dict[str, object]], case["answers"]),
            tmp_path / ("candidate" + source.suffix),
        )
        == case["expected"]
    )
