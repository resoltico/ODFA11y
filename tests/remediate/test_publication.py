# SPDX-License-Identifier: MPL-2.0
"""The application publishes explicitly; core candidates cannot change after verification."""

from pathlib import Path

import pytest

from odfa11y.application.remediate import remediate
from odfa11y.errors import DocumentRefusal, OutputOccupied
from odfa11y.odf import OdfDocument, Part, select_elements
from odfa11y.remediate import Candidate, PublicationState, execute_decisions
from odfa11y.remediate.compile import compile_decisions
from tests.fixtures.answers import metadata_input
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt


def test_existing_destination_needs_explicit_replace(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = reviewed_plan(source, [metadata_input(title="Reviewed")])
    destination = tmp_path / "candidate.odt"
    destination.write_bytes(b"keep")
    with pytest.raises(OutputOccupied):
        remediate(source, destination, plan)
    assert destination.read_bytes() == b"keep"
    result = remediate(source, destination, plan, replace=True)
    assert result.publication is PublicationState.PUBLISHED
    assert result.published
    assert destination.read_bytes() != b"keep"


def test_remediation_opens_the_captured_source_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = reviewed_plan(source, [metadata_input(title="Reviewed")])
    original = OdfDocument.open
    opened = []

    def open_document(path) -> OdfDocument:
        opened.append(path)
        return original(path)

    monkeypatch.setattr(OdfDocument, "open", staticmethod(open_document))
    result = remediate(source, tmp_path / "candidate.odt", plan)
    assert result.published
    assert len(opened) == 1
    assert Path(opened[0]).parent != source.parent


def test_changed_candidate_cannot_be_materialized(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = reviewed_plan(source, [metadata_input(title="Reviewed")])
    document = OdfDocument.open(source)
    decisions = compile_decisions(document, plan)
    candidate = execute_decisions(document, source, decisions, plan=plan)
    assert isinstance(candidate, Candidate)
    assert candidate.result.publication is PublicationState.PREVIEW
    assert list(tmp_path.iterdir()) == [source]
    select_elements(document.tree(Part.CONTENT), "//text:p")[0].text = "Unverified change"
    destination = tmp_path / "candidate.odt"
    with pytest.raises(DocumentRefusal, match="changed after"):
        candidate.materialize(destination)
    assert not destination.exists()
