# SPDX-License-Identifier: MPL-2.0
"""Kinds are judged by what documents say they are; families never leak into each other."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main
from odfa11y.content import GraphicAlternative
from odfa11y.families import REGISTRY
from odfa11y.families.generic import GenericAdapter
from odfa11y.families.text import SetGraphicAlternatives
from odfa11y.odf import Family, OdfDocument, Part, qn, select_elements
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.pipeline.profiles import profile_named
from odfa11y.remediation import SetMetadata, SetOdfVersion
from odfa11y.report import FactKeys, Location, Severity, rules
from odfa11y.source_audit import audit_odf

from .documents import OASIS, Variant, make_flat, make_package
from .operation_execution import assert_refused, execute_operations
from .reviewed_plans import reviewed_plan

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.report import Report


def ids(report: Report) -> set[str]:
    return {finding.rule_id for finding in report.findings}


def test_an_unrecognised_media_type_stops_the_audit_with_one_finding(tmp_path: Path) -> None:
    path = make_package(tmp_path, "text", Variant(media_type="application/epub+zip"))
    report = audit_odf(path)
    assert "ODF005" in ids(report)
    assert report.facts.get(FactKeys.DOCUMENT_ADAPTER) is None


def test_a_body_that_contradicts_the_media_type_is_an_error(tmp_path: Path) -> None:
    body = "<office:spreadsheet><table:table table:name='A'/></office:spreadsheet>"
    report = audit_odf(make_package(tmp_path, "text", Variant(body=body)))
    finding = next(f for f in report.findings if f.rule_id == "ODF006")
    assert finding.severity is Severity.ERROR
    assert finding.details == {"body": "office:spreadsheet", "expected": "office:text"}


def test_a_manifest_that_disagrees_with_the_mimetype_is_reported(tmp_path: Path) -> None:
    path = make_package(tmp_path, "text", Variant(manifest_media_type=OASIS + "spreadsheet"))
    assert "ODF004" in ids(audit_odf(path))


def test_a_misleading_extension_is_only_a_warning(tmp_path: Path) -> None:
    report = audit_odf(make_package(tmp_path, "text", Variant(extension=".ods")))
    finding = next(f for f in report.findings if f.rule_id == "ODF007")
    assert finding.severity is Severity.WARNING
    assert report.facts[FactKeys.DOCUMENT_KIND] == "text"  # the extension never selects the kind


def test_a_package_without_mimetype_falls_back_to_the_manifest(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "spreadsheet", Variant(mimetype=False)))
    assert document.kind is not None
    assert document.detection.declared_by == "manifest"
    report = audit_odf(document.storage.source)
    assert "PKG001" in ids(report)
    assert report.error_count == 0


@pytest.mark.parametrize(
    "media", ["application/vnd.sun.xml.base", "application/vnd.oasis.opendocument.database"]
)
def test_retired_database_media_types_are_rejected(tmp_path: Path, media: str) -> None:
    path = make_package(tmp_path, "database", Variant(media_type=media))
    report = audit_odf(path)
    assert "ODF005" in ids(report)
    assert OdfDocument.open(path).kind is None


def test_deprecated_image_documents_are_flagged(tmp_path: Path) -> None:
    assert "ODF008" in ids(audit_odf(make_package(tmp_path, "image")))


def test_a_flat_document_with_the_wrong_root_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "wrong.fodt"
    path.write_text('<?xml version="1.0"?><root/>', encoding="utf-8")
    assert "ODF010" in ids(audit_odf(path))


def test_a_flat_document_without_a_declared_media_type_is_unrecognised(tmp_path: Path) -> None:
    path = make_flat(tmp_path, "text")
    path.write_text(path.read_text().replace(f' office:mimetype="{OASIS}text"', ""))
    report = audit_odf(path)
    assert {"PKG001", "ODF005"} <= ids(report)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_a_text_plan_is_refused_for_every_other_family(
    tmp_path: Path, make: Callable[..., Path]
) -> None:
    source = make(tmp_path, "presentation")
    destination = tmp_path / "out"
    plan = [SetGraphicAlternatives({"Logo": GraphicAlternative("x")})]
    assert_refused(
        execute_operations(source, destination, plan),
        match="do not apply to a presentation document",
    )
    assert not destination.exists()


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_common_operations_apply_to_any_family_and_keep_the_body(
    tmp_path: Path, make: Callable[..., Path]
) -> None:
    source = make(tmp_path, "presentation")
    destination = tmp_path / f"out{source.suffix}"
    result = execute_operations(
        source, destination, [SetMetadata(title="New", language="de-DE"), SetOdfVersion("1.3")]
    )
    assert result.changed
    after = OdfDocument.open(destination)
    assert after.kind is not None
    assert after.kind.family is Family.PRESENTATION
    meta = select_elements(after.tree(Part.META), "//dc:title | //dc:language")
    assert {m.text for m in meta} == {"New", "de-DE"}
    assert after.tree(Part.CONTENT).getroot().get(qn("office", "version")) == "1.3"
    again = execute_operations(
        destination, tmp_path / f"again{source.suffix}", [SetMetadata(title="New")]
    )
    assert not again.changed


def test_a_flat_document_is_saved_byte_identically_when_untouched(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    destination = tmp_path / "copy.fodt"
    execute_operations(source, destination, [])
    assert destination.read_bytes() == source.read_bytes()


def test_setting_the_language_on_a_flat_text_document_edits_its_default_style(
    tmp_path: Path,
) -> None:
    source = make_flat(tmp_path, "text")
    destination = tmp_path / "out.fodt"
    execute_operations(source, destination, [SetMetadata(language="fr-FR")])
    report = audit_odf(destination)
    assert report.facts[FactKeys.DOCUMENT_LANGUAGE] == "fr-FR"
    assert "META003" not in ids(report)


def test_the_template_refuses_a_source_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.odt"
    broken.write_bytes(b"not a zip")
    status = main(["plan", str(broken)])
    captured = capsys.readouterr()
    assert status != 0
    assert not captured.out
    assert "PKG000" in captured.err
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
        SourceOnlyPresentation(),
    )
    source = make_package(tmp_path, "presentation")
    record = execute(
        source,
        reviewed_plan(source, [SetMetadata(title="T")], FidelityPolicy()),
        tmp_path / "out",
        RunSettings(),
    )
    statuses = {stage.name.value: stage.status for stage in record.stages}
    assert statuses["audit-remediated"] == "passed"
    for name in ("export-source", "export-remediated", "audit-pdf", "fidelity"):
        assert statuses[name] == "not-applicable", name
    assert statuses["validate-pdf"] == "skipped"  # not part of the verify profile
    assert record.passed
    run = json.loads((tmp_path / "out" / "run.json").read_text())
    assert run["document"]["kind"] == "presentation"
    assert run["document"]["adapter"] == "generic"
    assert (tmp_path / "out" / "remediated.odp").is_file()


def test_the_production_profile_fails_for_a_family_without_pdf_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        REGISTRY,
        Family.PRESENTATION,
        SourceOnlyPresentation(),
    )
    record = execute(
        make_package(tmp_path, "presentation"),
        reviewed_plan(make_package(tmp_path, "presentation"), [], FidelityPolicy()),
        tmp_path / "out",
        RunSettings(profile=profile_named("production")),
    )
    assert not record.passed
    failed = next(stage for stage in record.stages if stage.status == "failed")
    assert failed.name == "export-source"
    assert "requires PDF validation" in (failed.reason or "")


def test_a_new_family_needs_only_a_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def audit(_document: OdfDocument, report: Report) -> None:
        report.add(rules.ODF009, "Presentation adapter ran.", location=Location("document"))

    class CustomPresentation(SourceOnlyPresentation):
        name = "presentation"

    presentation = CustomPresentation()
    monkeypatch.setattr(presentation, "audit", audit)
    monkeypatch.setitem(REGISTRY, Family.PRESENTATION, presentation)
    report = audit_odf(make_package(tmp_path, "presentation"))
    assert report.facts[FactKeys.DOCUMENT_ADAPTER] == "presentation"
    assert any(f.message == "Presentation adapter ran." for f in report.findings)


def test_a_missing_version_is_not_reported_as_an_unbundled_one(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    source.write_text(source.read_text().replace(' office:version="1.4"', ""), encoding="utf-8")
    report = audit_odf(source, schema=True)
    finding = next(f for f in report.findings if f.rule_id == "SCHEMA002")
    assert "declares no ODF version" in finding.message


class SourceOnlyPresentation(GenericAdapter):
    """Exercise an implemented source family without a native export capability."""

    family = Family.PRESENTATION
