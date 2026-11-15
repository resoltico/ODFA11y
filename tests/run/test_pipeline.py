# SPDX-License-Identifier: MPL-2.0
"""The pipeline: fail-closed stages, evidence on failure, and the real end-to-end run."""

import json
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.errors import InvalidOption, OutputOccupied
from odfa11y.evidence import check_bundle
from odfa11y.odf import PackageStorage
from odfa11y.plans.fidelity import Pagination
from odfa11y.progress import PIPELINE_STAGES
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import PROFILES, profile_named
from tests.fixtures.answers import (
    graphic_answer,
    graphic_inputs,
    metadata_input,
)
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.schema import assert_record_schema
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.run.record import RunRecord


def statuses(record: RunRecord) -> dict[str, str]:
    """Map stage names to statuses.

    Returns
    -------
    dict[str, str]
        Stage statuses in order.

    """
    return {stage.name: stage.status for stage in record.stages}


def test_unreadable_source_stops_everything_but_still_publishes_evidence(tmp_path: Path) -> None:
    source = tmp_path / "broken.odt"
    source.write_bytes(b"not a zip")
    record = execute(source, reviewed_plan(source, [], Pagination.SAME()), tmp_path / "out")
    assert_record_schema(record)
    assert statuses(record)["audit-source"] == "failed"
    assert statuses(record)["identify-source"] == "passed"
    kept = {"identify-source", "audit-source"}
    assert all(s == "skipped" for name, s in statuses(record).items() if name not in kept)
    assert record.exit_status == 2
    assert check_bundle(tmp_path / "out") == []
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert (run["status"], run["failed_stage"]) == ("failed", "audit-source")


def test_remediation_failure_publishes_evidence_without_a_remediated_document(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    operations = [graphic_inputs({"Missing": graphic_answer("x")})]
    record = execute(source, reviewed_plan(source, operations, Pagination.SAME()), tmp_path / "out")
    assert statuses(record)["remediate"] == "failed"
    assert record.exit_status == 4
    assert not (tmp_path / "out" / "remediated.odt").exists()
    stages = {
        x["name"]: x for x in json.loads((tmp_path / "out" / "run.json").read_text())["stages"]
    }
    assert "Missing" in stages["remediate"]["reason"]
    assert check_bundle(tmp_path / "out") == []


def test_an_occupied_evidence_directory_is_refused_before_any_work(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    target = tmp_path / "out"
    target.mkdir()
    (target / "keep.txt").write_text("precious")
    with pytest.raises(OutputOccupied):
        execute(source, reviewed_plan(source, [], Pagination.SAME()), target)
    assert [p.name for p in target.iterdir()] == ["keep.txt"]


def test_a_missing_libreoffice_fails_the_export_stage_and_keeps_earlier_evidence(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = RunSettings(tools=Tools(soffice=str(tmp_path / "no-such-soffice")))
    record = execute(
        source,
        reviewed_plan(source, [metadata_input(title="T")], Pagination.SAME()),
        tmp_path / "out",
        options,
    )
    assert statuses(record)["remediate"] == "passed"
    assert statuses(record)["export-source"] == "failed"
    assert record.exit_status == 3
    assert (tmp_path / "out" / "remediated.odt").is_file()


def test_the_record_lists_every_stage_in_order(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    record = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        tmp_path / "out",
        RunSettings(tools=Tools(soffice="nope")),
    )
    assert tuple(stage.name for stage in record.stages) == PIPELINE_STAGES


def _document_with_spacers(tmp_path: Path) -> Path:
    source = make_minimal_odt(tmp_path / "spacers.odt", features={"add_blank_body_paragraph": True})
    package = PackageStorage(source)
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(
            b'<text:p text:style-name="Body"/>',
            b'<text:p text:style-name="Body"/><text:p text:style-name="Body"/>'
            b'<text:p text:style-name="Body">Text after the spacers moves up.</text:p>',
        ),
    )
    shifted = tmp_path / "with-spacers.odt"
    package.save(shifted)
    return shifted


def test_an_unreadable_source_still_yields_an_evidence_bundle(tmp_path: Path) -> None:
    record = execute(
        tmp_path / "absent.odt",
        reviewed_plan(tmp_path / "absent.odt", [], Pagination.SAME()),
        tmp_path / "out",
    )
    assert statuses(record)["identify-source"] == "failed"
    assert record.exit_status == 3
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["document"] == {
        "name": "absent.odt",
        "sha256": None,
        "kind": None,
        "media_type": None,
        "layout": None,
        "family": None,
        "adapter": None,
        "odf_version": None,
    }
    assert (run["status"], run["failed_stage"]) == ("failed", "identify-source")
    assert check_bundle(tmp_path / "out") == []
    assert "absent.odt" in (tmp_path / "out" / "REVIEW.md").read_text()


def test_a_profile_runs_only_its_stages_and_records_the_rest_as_skipped(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = RunSettings(profile=profile_named("source"))
    record = execute(
        source,
        reviewed_plan(source, [metadata_input(title="T")], Pagination.SAME()),
        tmp_path / "o",
        options,
    )
    expected = {
        name: "passed" if name in PROFILES["source"].stages else "skipped"
        for name in PIPELINE_STAGES
    }
    assert statuses(record) == expected
    assert record.exit_status == 0
    skipped = [s for s in record.stages if s.name == "export-source"]
    assert skipped[0].reason == "not part of the source profile"
    run = json.loads((tmp_path / "o" / "run.json").read_text())
    assert run["profile"] == PROFILES["source"].as_dict()


def test_an_unknown_profile_is_a_configuration_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(InvalidOption, match="Unknown profile"):
        execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            tmp_path / "o",
            RunSettings(profile=profile_named("x")),
        )
    assert not (tmp_path / "o").exists()


def test_the_production_profile_fails_at_export_when_libreoffice_is_unavailable(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = RunSettings(
        tools=Tools(soffice=str(tmp_path / "none")), profile=profile_named("production")
    )
    record = execute(source, reviewed_plan(source, [], Pagination.SAME()), tmp_path / "o", options)
    assert statuses(record)["export-source"] == "failed"
    assert record.strict
