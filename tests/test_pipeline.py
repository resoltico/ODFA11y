# SPDX-License-Identifier: MPL-2.0
"""The pipeline: fail-closed stages, evidence on failure, and the real end-to-end run."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import OutputError
from odfa11y.evidence import check_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdtPackage
from odfa11y.pipeline import STAGE_NAMES, PipelineOptions, run_pipeline
from odfa11y.remediation import (
    AltText,
    RemoveEmptySpacers,
    SetAltText,
    SetMetadata,
)

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.pipeline import RunRecord


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
    record = run_pipeline(source, [], FidelityPolicy(), tmp_path / "out")
    assert statuses(record)["audit-source"] == "failed"
    assert all(s == "skipped" for name, s in statuses(record).items() if name != "audit-source")
    assert record.exit_status == 2
    assert check_bundle(tmp_path / "out") == []
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert (run["status"], run["failed_stage"]) == ("failed", "audit-source")


def test_remediation_failure_publishes_evidence_without_a_remediated_document(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    operations = [SetAltText({"Missing": AltText("x")})]
    record = run_pipeline(source, operations, FidelityPolicy(), tmp_path / "out")
    assert statuses(record)["remediate"] == "failed"
    assert record.exit_status == 3
    assert not (tmp_path / "out" / "remediated.odt").exists()
    assert (
        "Missing" in json.loads((tmp_path / "out" / "run.json").read_text())["stages"][1]["reason"]
    )
    assert check_bundle(tmp_path / "out") == []


def test_an_occupied_evidence_directory_is_refused_before_any_work(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    target = tmp_path / "out"
    target.mkdir()
    (target / "keep.txt").write_text("precious")
    with pytest.raises(OutputError):
        run_pipeline(source, [], FidelityPolicy(), target)
    assert [p.name for p in target.iterdir()] == ["keep.txt"]


def test_a_missing_libreoffice_fails_the_export_stage_and_keeps_earlier_evidence(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = PipelineOptions(soffice=str(tmp_path / "no-such-soffice"))
    record = run_pipeline(
        source, [SetMetadata(title="T")], FidelityPolicy(), tmp_path / "out", options
    )
    assert statuses(record)["remediate"] == "passed"
    assert statuses(record)["export-source"] == "failed"
    assert record.exit_status == 3
    assert (tmp_path / "out" / "remediated.odt").is_file()


def test_the_record_lists_every_stage_in_order(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    record = run_pipeline(
        source, [], FidelityPolicy(), tmp_path / "out", PipelineOptions(soffice="nope")
    )
    assert tuple(stage.name for stage in record.stages) == STAGE_NAMES


@pytest.mark.integration
def test_end_to_end_run_with_libreoffice_and_verapdf_produces_verified_evidence(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = make_minimal_odt(
        tmp_path / "doc.odt",
        with_plain_email=True,
        with_data_table=True,
        with_image_without_alt=True,
    )
    operations = [
        SetMetadata(title="Evidence run", language="en-GB"),
        SetAltText({"Logo": AltText("Logo", "A sample logo")}),
    ]
    options = PipelineOptions(soffice=soffice, verapdf_path=verapdf)
    record = run_pipeline(source, operations, FidelityPolicy(), tmp_path / "out", options)
    assert statuses(record) == dict.fromkeys(STAGE_NAMES, "passed") | {"audit-source": "passed"}
    assert record.exit_status == 0
    assert check_bundle(tmp_path / "out") == []
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["toolchain"]["LibreOffice"]["version"] != "unknown"
    assert run["toolchain"]["veraPDF"]["name"] == "veraPDF"
    assert set(run["outputs"]) >= {"remediated.odt", "remediated.pdf", "source.pdf", "verapdf.xml"}
    assert "- [ ]" in (tmp_path / "out" / "REVIEW.md").read_text()


@pytest.mark.integration
def test_layout_shifting_operations_fail_the_default_fidelity_gate_and_leave_diff_images(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = _document_with_spacers(tmp_path)
    options = PipelineOptions(soffice=soffice)
    failed = run_pipeline(
        source, [RemoveEmptySpacers()], FidelityPolicy(), tmp_path / "strict", options
    )
    assert statuses(failed)["fidelity"] == "failed"
    assert failed.exit_status == 2
    assert (tmp_path / "strict" / "fidelity" / "page-001-diff.png").is_file()
    allowed = FidelityPolicy(pagination="may-change")
    passed = run_pipeline(source, [RemoveEmptySpacers()], allowed, tmp_path / "relaxed", options)
    assert statuses(passed)["fidelity"] == "passed"


@pytest.mark.integration
def test_repeated_runs_have_equal_logical_results_and_identical_documents(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    source = make_minimal_odt(tmp_path / "doc.odt")
    options = PipelineOptions(soffice=soffice)
    runs = [
        run_pipeline(
            source, [SetMetadata(title="Same")], FidelityPolicy(), tmp_path / f"r{i}", options
        )
        for i in range(2)
    ]
    first, second = (json.loads((tmp_path / f"r{i}" / "run.json").read_text()) for i in range(2))
    assert first["stages"] == second["stages"]
    assert first["operations"] == second["operations"]
    assert first["outputs"]["remediated.odt"] == second["outputs"]["remediated.odt"]
    assert runs[0].passed


def _document_with_spacers(tmp_path: Path) -> Path:
    source = make_minimal_odt(tmp_path / "spacers.odt", add_blank_body_paragraph=True)
    package = OdtPackage(source)
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
