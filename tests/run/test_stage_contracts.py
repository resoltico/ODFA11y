# SPDX-License-Identifier: MPL-2.0
"""Negative controls for the delivered artifact-dependent execution mechanism."""

import importlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from odfa11y.application import run
from odfa11y.concepts.review import ReviewTopic
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.errors import ToolFailure
from odfa11y.evidence import check_bundle
from odfa11y.native.verapdf import ValidationOutput
from odfa11y.odf import OdfDocument, PackageStorage, Part, select_elements
from odfa11y.progress import Stage
from odfa11y.remediate.execute import execute_decisions
from odfa11y.remediate.result import PublicationState
from odfa11y.rules import registry as rules
from odfa11y.run.record import StageResult
from odfa11y.status import (
    Crashed,
    GateFailed,
    NotApplicable,
    Passed,
    Profile,
    Refused,
    Skipped,
    SkipReason,
)
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.answers import fault_input, materialize, metadata_input
from tests.fixtures.native import native_fakes, recording
from tests.fixtures.pdf import text_pdf
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.records import record
from tests.fixtures.verapdf import REPORT
from tests.fixtures.writer import make_minimal_odt


def test_skips_and_inapplicability_never_change_run_acceptance() -> None:

    result = replace(
        record(),
        stages=(
            StageResult(Stage.FIDELITY, Skipped(SkipReason.MISSING_INPUT, Stage.EXPORT_SOURCE)),
            StageResult(Stage.EXPORT_REMEDIATED, NotApplicable("No native PDF export")),
        ),
        profile=Profile.PRODUCTION,
    )
    assert result.exit_status == 0
    assert result.passed


@pytest.mark.parametrize(("profile", "expected"), [(Profile.PDF, 0), (Profile.PRODUCTION, 1)])
def test_only_production_rejects_candidate_warnings(tmp_path: Path, profile, expected) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt", features={"with_plain_email": True})
    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        profile=profile,
        native_tools=native_fakes(),
    )
    assert result.exit_status == expected
    assert (tmp_path / "bundle" / "remediated.pdf").is_file()


def test_preservation_refusal_produces_no_candidate_export(tmp_path: Path, monkeypatch) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    plan = reviewed_plan(source)

    def corrupt(document, decision):
        select_elements(document.tree(Part.CONTENT), "//text:p")[0].text = "Lost authored words"
        return EditResult((Outcome(decision.kind.id, Status.APPLIED, "Unallowed change"),))

    def execute_fault(document, source, decisions, *, plan):
        faulty = materialize(document, [fault_input(metadata_input(title="Reviewed"), corrupt)])
        return execute_decisions(document, source, faulty, plan=plan)

    monkeypatch.setattr(
        importlib.import_module("odfa11y.run.stages"), "execute_decisions", execute_fault
    )
    calls = []
    result = run(
        source,
        plan,
        tmp_path / "bundle",
        native_tools=replace(native_fakes(), export=recording(calls)),
    )
    stages = {stage.name: stage for stage in result.stages}
    refusal = stages[Stage.REMEDIATE].outcome
    assert isinstance(refusal, Refused)
    assert "content changed" in str(refusal.error)
    assert stages[Stage.EXPORT_REMEDIATED].outcome == Skipped(
        SkipReason.MISSING_INPUT, Stage.REMEDIATE
    )
    assert len(calls) == 1  # the captured source only
    assert not (tmp_path / "bundle" / "remediated.odt").exists()
    assert not (tmp_path / "bundle" / "remediated.pdf").exists()


@pytest.mark.parametrize("tables", [False, True])
def test_human_checklist_tracks_observed_table_presence(tmp_path: Path, tables: bool) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt", features={"with_data_table": tables})
    result = run(source, reviewed_plan(source), tmp_path / "bundle", profile=Profile.SOURCE)
    assert (ReviewTopic.TABLE_HEADERS in {item.key for item in result.human_review}) is tables
    review = (tmp_path / "bundle" / "REVIEW.md").read_text()
    assert ("Whether table header cells" in review) is tables
    assert review.index("## Needs a human") < review.index("## Gates")


def test_run_opens_once_and_reuses_context_analysis_per_document_state(
    tmp_path: Path, monkeypatch
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    plan = reviewed_plan(source, [metadata_input(title="Changed")])
    original = OdfDocument.open
    opens = []

    def open_once(path):
        opens.append(path)
        return original(path)

    monkeypatch.setattr(OdfDocument, "open", staticmethod(open_once))
    context = importlib.import_module("odfa11y.odf.export_context")
    analyze = context._analyze_export_context
    analyses = []

    def observe(document):
        analyses.append(document)
        return analyze(document)

    monkeypatch.setattr(context, "_analyze_export_context", observe)
    result = run(source, plan, tmp_path / "bundle", native_tools=native_fakes())
    assert result.exit_status == 0
    assert len(opens) == 1
    assert len(analyses) == 2  # original and edited candidate


def test_undeclared_scratch_file_is_not_published(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    native = native_fakes()

    def export(path, output, settings):
        (output.parent / "unrelated.txt").write_text("Not declared evidence")
        return native.export(path, output, settings)

    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        native_tools=replace(native, export=export),
    )
    assert result.exit_status == 0
    assert not (tmp_path / "bundle" / "unrelated.txt").exists()


def test_difference_image_is_declared_and_inventoried(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")

    def export(path, output, settings):
        return text_pdf(
            output,
            [["The same words move vertically."]],
            top=140 if path.name.startswith("remediated") else 180,
        )

    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        native_tools=replace(native_fakes(), export=export),
    )
    fidelity = next(stage for stage in result.stages if stage.name == Stage.FIDELITY)
    assert fidelity.report is not None
    assert rules.FIDELITY005.id in {finding.rule_id for finding in fidelity.report.findings}
    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text())
    assert "diff/page-001-diff.png" in manifest["files"]
    assert check_bundle(tmp_path / "bundle") == []


def test_unreadable_source_audit_establishes_no_remediation_or_export_input(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    package = PackageStorage(source)
    package.write_member("styles.xml", b"<broken")
    package.save(source)
    calls = []
    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        native_tools=replace(native_fakes(), export=recording(calls)),
    )
    outcomes = {stage.name: stage.outcome for stage in result.stages}
    assert isinstance(outcomes[Stage.AUDIT_SOURCE], GateFailed)
    assert outcomes[Stage.REMEDIATE] == Skipped(SkipReason.MISSING_INPUT, Stage.AUDIT_SOURCE)
    assert outcomes[Stage.EXPORT_SOURCE] == Skipped(SkipReason.MISSING_INPUT, Stage.AUDIT_SOURCE)
    assert not calls
    assert not (tmp_path / "bundle" / "remediated.odt").exists()
    assert result.exit_status == 2


def test_run_record_describes_the_published_candidate_not_an_internal_preview(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    result = run(source, reviewed_plan(source), tmp_path / "bundle", profile=Profile.SOURCE)
    remediation = next(
        stage.remediation for stage in result.stages if stage.name == Stage.REMEDIATE
    )
    assert remediation is not None
    assert remediation.publication is PublicationState.PUBLISHED
    assert remediation.destination == tmp_path / "bundle" / "remediated.odt"
    assert remediation.destination.is_file()


def test_incomplete_noncompliant_validation_cannot_pass_production(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    xml = REPORT.format(status="normal", compliant="false", failed=1, rules="").encode()
    native = replace(
        native_fakes(),
        validate=lambda *args, **kwargs: ValidationOutput(xml, "", ToolIdentity("veraPDF", "test")),
    )
    result = run(
        source,
        reviewed_plan(source),
        tmp_path / "bundle",
        profile=Profile.PRODUCTION,
        native_tools=native,
    )
    outcomes = {stage.name: stage.outcome for stage in result.stages}
    validation = outcomes[Stage.VALIDATE_PDF]
    assert isinstance(validation, Crashed)
    assert isinstance(validation.error, ToolFailure)
    assert isinstance(outcomes[Stage.FIDELITY], Passed)
    assert result.exit_status == 3
    assert result.failed_stage is Stage.VALIDATE_PDF
    assert "PDF/UA conformance was not established" in (tmp_path / "bundle/REVIEW.md").read_text()
