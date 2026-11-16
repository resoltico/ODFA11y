# SPDX-License-Identifier: MPL-2.0
"""Refusals retain actionable targets and distinguish source from tool failures."""

lazy from pathlib import Path

import pytest

from odfa11y import DocumentRefusal, PlanError, RemedyAction
from odfa11y.cli import main
from odfa11y.plans.codec import parse_tables
from odfa11y.plans.registry import registered_kinds
from odfa11y.run.native import export_document
from tests.fixtures.native import native_fakes
from tests.fixtures.native_resources import writer_resource
from tests.fixtures.plans import plan_header


def test_linked_image_refusal_names_the_frame_and_embedding_action(tmp_path: Path) -> None:
    source = writer_resource(tmp_path, "https://example.test/remote.png")
    destination = tmp_path / "publication.pdf"
    with pytest.raises(DocumentRefusal) as caught:
        export_document(source, destination, native_tools=native_fakes())
    assert caught.value.exit_status == 2
    assert caught.value.remedy is not None
    assert caught.value.remedy.action is RemedyAction.EMBED_RESOURCE
    assert caught.value.remedy.target == "frame 'Asset'"
    assert "remote.png" in str(caught.value)
    assert not destination.exists()


def test_corrupt_source_is_refused_by_audit_and_remediate(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.odt"
    source.write_bytes(b"not an OpenDocument container")
    plan = tmp_path / "plan.toml"
    plan.write_text(plan_header(source))
    assert main(["audit", str(source), "--format", "json"]) == 2
    destination = tmp_path / "candidate.odt"
    assert main(["remediate", str(source), str(destination), "--plan", str(plan)]) == 2
    assert not destination.exists()


def test_old_plan_header_has_a_regeneration_remedy() -> None:
    with pytest.raises(PlanError) as caught:
        parse_tables({"plan": {"format": 1}}, registered_kinds())
    assert caught.value.exit_status == 4
    assert caught.value.remedy is not None
    assert caught.value.remedy.action is RemedyAction.REGENERATE_PLAN
    assert "schema_version" in str(caught.value)


def test_error_envelopes_bound_each_diagnostic_without_dropping_plan_problems() -> None:
    error = PlanError("m" * 5000, problems=("a" * 5000, "b" * 5000, "c" * 5000), details="d" * 5000)
    record = error.as_record()
    assert record.message == "m" * 4096
    assert record.problems == ("a" * 4096, "b" * 4096, "c" * 4096)
    assert record.details == "d" * 4096
    assert str(error).count("\n") == 3
