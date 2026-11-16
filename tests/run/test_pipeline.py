# SPDX-License-Identifier: AGPL-3.0-only
"""Preparation is effect-free; completed artifacts drive independent run stages."""

from dataclasses import replace
from pathlib import Path

import pytest

from odfa11y.application import run
from odfa11y.application.tools import Tools
from odfa11y.errors import (
    DocumentRefusal,
    IoFailure,
    OutputOccupied,
    PackageError,
    PlanError,
    ToolUnavailable,
)
from odfa11y.evidence import check_bundle
from odfa11y.progress import Stage
from odfa11y.run.stages import STAGES
from odfa11y.status import GateFailed, Passed, Profile, Skipped, SkipReason
from tests.fixtures.answers import graphic_answer, graphic_inputs
from tests.fixtures.native import native_fakes, recording, validation_result
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.schema import assert_record_schema
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("profile", tuple(Profile))
def test_record_declares_every_stage_and_profile_eligibility(
    tmp_path: Path, profile: Profile
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        profile=profile,
        native_tools=native_fakes(),
    )
    assert tuple(stage.name for stage in result.stages) == tuple(spec.name for spec in STAGES)
    for spec, stage in zip(STAGES, result.stages, strict=True):
        assert isinstance(stage.outcome, Skipped) == (profile < spec.minimum)
    assert result.profile is profile
    assert_record_schema(result)
    assert check_bundle(tmp_path / "bundle") == []


@pytest.mark.parametrize("payload", [None, b"not an ODF package"])
def test_unreadable_source_preparation_leaves_no_bundle(
    tmp_path: Path, payload: bytes | None
) -> None:
    source = tmp_path / "broken.odt"
    if payload is not None:
        source.write_bytes(payload)
    plan = reviewed_plan(source)
    with pytest.raises(IoFailure if payload is None else PackageError):
        run(source, plan, tmp_path / "bundle", profile=Profile.SOURCE)
    assert not (tmp_path / "bundle").exists()


def test_stale_target_is_a_preparation_error_without_evidence(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    plan = reviewed_plan(source, [graphic_inputs({"Missing": graphic_answer("description")})])
    with pytest.raises(PlanError):
        run(source, plan, tmp_path / "bundle", profile=Profile.SOURCE)
    assert not (tmp_path / "bundle").exists()


@pytest.mark.parametrize("profile", [Profile.PDF, Profile.PRODUCTION])
def test_required_office_absence_is_a_preparation_failure(tmp_path: Path, profile: Profile) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    with pytest.raises(ToolUnavailable):
        run(
            source,
            reviewed_plan(source),
            tmp_path / "bundle",
            profile=profile,
            tools=Tools(soffice=tmp_path / "missing"),
        )
    assert not (tmp_path / "bundle").exists()


def test_occupied_output_is_refused_without_altering_contents(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    target = tmp_path / "bundle"
    target.mkdir()
    (target / "keep").write_text("precious")
    with pytest.raises(OutputOccupied):
        run(source, reviewed_plan(source), target, profile=Profile.SOURCE)
    assert (target / "keep").read_text() == "precious"


def test_candidate_findings_do_not_block_export_or_pdf_checks(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt", features={"with_image_without_alt": True})
    calls = []
    native = replace(native_fakes(), export=recording(calls))
    result = run(source, reviewed_plan(source), tmp_path / "bundle", native_tools=native)
    outcomes = {stage.name: stage.outcome for stage in result.stages}
    assert isinstance(outcomes[Stage.AUDIT_REMEDIATED], GateFailed)
    assert isinstance(outcomes[Stage.EXPORT_REMEDIATED], Passed)
    assert not isinstance(outcomes[Stage.AUDIT_PDF], Skipped)
    assert isinstance(outcomes[Stage.FIDELITY], Passed)
    assert len(calls) == 2
    assert result.exit_status == 2
    assert (tmp_path / "bundle" / "remediated.pdf").is_file()


def test_validator_gate_failure_does_not_block_fidelity(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    native = replace(native_fakes(), validate=lambda *_args, **_kwargs: validation_result(False))
    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        profile=Profile.PRODUCTION,
        native_tools=native,
    )
    outcomes = {stage.name: stage.outcome for stage in result.stages}
    assert isinstance(outcomes[Stage.VALIDATE_PDF], GateFailed)
    assert isinstance(outcomes[Stage.FIDELITY], Passed)
    assert result.exit_status == 2
    assert check_bundle(tmp_path / "bundle") == []


def test_export_refusal_skips_only_stages_missing_its_artifact(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    native = native_fakes()
    original = native.export

    def refuse_candidate(path, output, settings):
        if path.name.startswith("remediated"):
            message = "Controlled candidate export refusal"
            raise DocumentRefusal(message)
        return original(path, output, settings)

    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        native_tools=replace(native, export=refuse_candidate),
    )
    outcomes = {stage.name: stage.outcome for stage in result.stages}
    assert isinstance(outcomes[Stage.EXPORT_SOURCE], Passed)
    assert outcomes[Stage.AUDIT_PDF] == Skipped(SkipReason.MISSING_INPUT, Stage.EXPORT_REMEDIATED)
    assert outcomes[Stage.FIDELITY] == Skipped(SkipReason.MISSING_INPUT, Stage.EXPORT_REMEDIATED)
    assert not (tmp_path / "bundle" / "remediated.pdf").exists()
    assert check_bundle(tmp_path / "bundle") == []
