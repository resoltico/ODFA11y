# SPDX-License-Identifier: MPL-2.0
"""Kinds are judged by what documents say they are; families never leak into each other."""

import json
from collections.abc import Callable
from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.audit.package import PackageMeasurements
from odfa11y.cli import main
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.errors import PlanError
from odfa11y.families import REGISTRY
from odfa11y.families.spec import Unsupported
from odfa11y.odf import Family, OdfDocument, Part, qn, select_elements
from odfa11y.plans.fidelity import Pagination
from odfa11y.report import Location, Severity
from odfa11y.rules import registry as rules
from odfa11y.status import Profile, Refused
from tests.fixtures.answers import (
    metadata_input,
    version_input,
)
from tests.fixtures.documents import OASIS, Variant, make_flat, make_package
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native import native_fakes
from tests.fixtures.operations import apply_answers
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import RunSettings, execute
lazy from odfa11y.report import Report
lazy from tests.fixtures.answers import address_input


def ids(report: Report) -> set[str]:
    return {finding.rule_id for finding in report.findings}


def test_an_unrecognised_media_type_stops_the_audit_with_one_finding(tmp_path: Path) -> None:
    path = make_package(tmp_path, "text", Variant(media_type="application/epub+zip"))
    report = audit_odf(path)
    assert rules.ODF006.id in ids(report)
    assert measurement(report, PackageMeasurements).family is None


def test_a_body_that_contradicts_the_media_type_is_an_error(tmp_path: Path) -> None:
    body = "<office:spreadsheet><table:table table:name='A'/></office:spreadsheet>"
    report = audit_odf(make_package(tmp_path, "text", Variant(body=body)))
    finding = next(f for f in report.findings if f.rule_id == rules.ODF007.id)
    assert finding.severity is Severity.ERROR
    assert finding.details == {"body": "office:spreadsheet", "expected": "office:text"}


def test_a_manifest_that_disagrees_with_the_mimetype_is_reported(tmp_path: Path) -> None:
    path = make_package(tmp_path, "text", Variant(manifest_media_type=OASIS + "spreadsheet"))
    assert rules.ODF005.id in ids(audit_odf(path))


def test_a_misleading_extension_is_only_a_warning(tmp_path: Path) -> None:
    report = audit_odf(make_package(tmp_path, "text", Variant(extension=".ods")))
    finding = next(f for f in report.findings if f.rule_id == rules.ODF008.id)
    assert finding.severity is Severity.WARNING
    assert (
        measured(measurement(report, PackageMeasurements).kind) == "text"
    )  # the extension never selects the kind


def test_a_package_without_mimetype_falls_back_to_the_manifest(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "spreadsheet", Variant(mimetype=False)))
    assert document.kind is not None
    assert document.detection.declared_by == "manifest"
    report = audit_odf(document.storage.source)
    assert rules.PKG003.id in ids(report)
    assert report.error_count == 0


@pytest.mark.parametrize(
    "media", ["application/vnd.sun.xml.base", "application/vnd.oasis.opendocument.database"]
)
def test_retired_database_media_types_are_rejected(tmp_path: Path, media: str) -> None:
    path = make_package(tmp_path, "database", Variant(media_type=media))
    report = audit_odf(path)
    assert rules.ODF006.id in ids(report)
    assert OdfDocument.open(path).kind is None


def test_deprecated_image_documents_are_flagged(tmp_path: Path) -> None:
    assert rules.ODF009.id in ids(audit_odf(make_package(tmp_path, "image")))


def test_a_flat_document_with_the_wrong_root_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "wrong.fodt"
    path.write_text('<?xml version="1.0"?><root/>', encoding="utf-8")
    assert rules.ODF011.id in ids(audit_odf(path))


def test_a_flat_document_without_a_declared_media_type_is_unrecognised(tmp_path: Path) -> None:
    path = make_flat(tmp_path, "text")
    path.write_text(path.read_text().replace(f' office:mimetype="{OASIS}text"', ""))
    report = audit_odf(path)
    assert {rules.PKG002.id, rules.ODF006.id} <= ids(report)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_a_text_plan_is_refused_for_every_other_family(
    tmp_path: Path, make: Callable[..., Path]
) -> None:
    source = make(tmp_path, "presentation")
    destination = tmp_path / "out"
    before = source.read_bytes()
    with pytest.raises(PlanError, match="does not apply"):
        apply_answers(source, destination, [address_input()])
    assert not destination.exists()
    assert source.read_bytes() == before


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_common_operations_apply_to_any_family_and_keep_the_body(
    tmp_path: Path, make: Callable[..., Path]
) -> None:
    source = make(tmp_path, "presentation")
    destination = tmp_path / f"out{source.suffix}"
    result = apply_answers(
        source, destination, [metadata_input(title="New", language="de-DE"), version_input("1.3")]
    )
    assert result.changed
    after = OdfDocument.open(destination)
    assert after.kind is not None
    assert after.kind.family is Family.PRESENTATION
    meta = select_elements(after.tree(Part.META), "//dc:title | //dc:language")
    assert {m.text for m in meta} == {"New", "de-DE"}
    assert after.tree(Part.CONTENT).getroot().get(qn("office", "version")) == "1.3"
    again = apply_answers(
        destination, tmp_path / f"again{source.suffix}", [metadata_input(title="New")]
    )
    assert not again.changed


def test_a_flat_document_is_saved_byte_identically_when_untouched(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    destination = tmp_path / "copy.fodt"
    apply_answers(source, destination, [])
    assert destination.read_bytes() == source.read_bytes()


def test_setting_the_language_on_a_flat_text_document_edits_its_default_style(
    tmp_path: Path,
) -> None:
    source = make_flat(tmp_path, "text")
    destination = tmp_path / "out.fodt"
    apply_answers(source, destination, [metadata_input(language="fr-FR")])
    report = audit_odf(destination)
    assert measurement(report, DocumentMetadata).language == "fr-FR"
    assert rules.META003.id not in ids(report)


def test_the_template_refuses_a_source_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.odt"
    broken.write_bytes(b"not a zip")
    status = main(["plan", str(broken)])
    captured = capsys.readouterr()
    assert status != 0
    assert not captured.out
    assert rules.PKG001.id in captured.err
    status = main(["plan", str(tmp_path / "missing.odt")])
    assert status != 0
    assert "No plan" in capsys.readouterr().err


def test_a_pipeline_for_a_family_without_export_marks_pdf_stages_not_applicable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        REGISTRY,
        Family.PRESENTATION,
        replace(
            REGISTRY[Family.PRESENTATION],
            export=Unsupported("No PDF export is defined for this test family."),
            audit=_source_only,
        ),
    )
    source = make_package(tmp_path, "presentation")
    record = execute(
        source,
        reviewed_plan(source, [metadata_input(title="T")], Pagination.SAME()),
        tmp_path / "out",
        RunSettings(),
        native_tools=native_fakes(),
    )
    statuses = {stage.name.value: stage.outcome.status for stage in record.stages}
    assert statuses["audit-remediated"] == "passed"
    for name in ("export-source", "export-remediated"):
        assert statuses[name] == "not-applicable", name
    assert statuses["audit-pdf"] == statuses["fidelity"] == "skipped"
    assert statuses["validate-pdf"] == "skipped"  # not part of the verify profile
    assert record.passed
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["document"]["kind"] == "presentation"
    assert run["document"]["family"] == "presentation"
    assert (tmp_path / "out" / "remediated.odp").is_file()


def test_the_production_profile_fails_for_a_family_without_pdf_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        REGISTRY,
        Family.PRESENTATION,
        replace(
            REGISTRY[Family.PRESENTATION],
            export=Unsupported("No PDF export is defined for this test family."),
            audit=_source_only,
        ),
    )
    record = execute(
        make_package(tmp_path, "presentation"),
        reviewed_plan(make_package(tmp_path, "presentation"), [], Pagination.SAME()),
        tmp_path / "out",
        RunSettings(profile=Profile.parse("production")),
        native_tools=native_fakes(),
    )
    assert not record.passed
    failed = next(stage for stage in record.stages if stage.outcome.status == "refused")
    assert failed.name == "export-source"
    outcome = failed.outcome
    assert isinstance(outcome, Refused)
    assert "No PDF export" in str(outcome.error)


def test_a_new_family_needs_only_a_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def audit(_document: OdfDocument, report: Report, _metadata: DocumentMetadata) -> None:
        report.raise_(rules.ODF010, "Presentation adapter ran.", location=Location("document"))

    presentation = replace(REGISTRY[Family.PRESENTATION], audit=audit)
    monkeypatch.setitem(REGISTRY, Family.PRESENTATION, presentation)
    report = audit_odf(make_package(tmp_path, "presentation"))
    assert measured(measurement(report, PackageMeasurements).family) == "presentation"
    assert any(f.message == "Presentation adapter ran." for f in report.findings)


def test_a_missing_version_is_not_reported_as_an_unbundled_one(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    source.write_text(source.read_text().replace(' office:version="1.4"', ""), encoding="utf-8")
    report = audit_odf(source, schema=True)
    finding = next(f for f in report.findings if f.rule_id == rules.SCHEMA002.id)
    assert "declares no ODF version" in finding.message


def _source_only(_document: OdfDocument, report: Report, _metadata: DocumentMetadata) -> None:
    report.raise_(rules.ODF010, "Controlled source-only family audit.")
