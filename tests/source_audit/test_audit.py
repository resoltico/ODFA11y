# SPDX-License-Identifier: MPL-2.0
"""Report accessibility findings for synthetic ODT documents."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from odfa11y.odf import PackageStorage
from odfa11y.plans import load_plan
from odfa11y.report import RULES, FactKeys, Location, Severity
from odfa11y.source_audit import audit_odf, prepare_plan
from tests.fixtures.plans import question_for
from tests.fixtures.writer import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report
    from tests.fixtures.writer import Features


def ids(report: Report) -> set[str]:
    """Collect the rule identifiers emitted by an audit.

    Returns
    -------
    set[str]
        The emitted rule identifiers.

    """
    return {finding.rule_id for finding in report.findings}


def test_minimal_document_passes_core_audit(tmp_path: Path) -> None:
    report = audit_odf(make_minimal_odt(tmp_path / "ok.odt"))
    assert report.error_count == 0
    assert report.facts[FactKeys.DOCUMENT_ODF_VERSION] == "1.4"


def test_older_consistent_version_is_reported_not_rejected(tmp_path: Path) -> None:
    report = audit_odf(make_minimal_odt(tmp_path / "old.odt", version="1.3"))
    assert report.error_count == 0
    assert report.facts[FactKeys.DOCUMENT_ODF_VERSION] == "1.3"


def test_members_declaring_different_versions_are_an_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "mixed.odt")
    package = PackageStorage(source)
    package.write_member("meta.xml", package.read("meta.xml").replace(b'"1.4"', b'"1.3"'))
    package.save(tmp_path / "mixed2.odt")
    assert "ODF001" in ids(audit_odf(tmp_path / "mixed2.odt"))


def test_audit_detects_plain_email_and_data_table_header(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "issues.odt", features={"with_plain_email": True, "with_data_table": True}
    )
    report = audit_odf(source)
    assert {"LINK001", "TABLE003"} <= ids(report)
    table = next(f for f in report.findings if f.rule_id == "TABLE003")
    assert table.details["table"] == "Data"
    assert question_for(report, table).kind.id == "table.headers"


def test_audit_detects_missing_graphic_alt_text(tmp_path: Path) -> None:
    report = audit_odf(
        make_minimal_odt(tmp_path / "image.odt", features={"with_image_without_alt": True})
    )
    finding = next(f for f in report.findings if f.rule_id == "GRAPHIC003")
    assert finding.severity is Severity.ERROR
    assert finding.details["frame"] == "Logo"
    assert question_for(report, finding).kind.id == "graphic.alternative"


def test_every_emitted_rule_is_registered(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "all.odt",
        features={
            "with_plain_email": True,
            "with_data_table": True,
            "with_image_without_alt": True,
        },
    )
    assert ids(audit_odf(source)) <= set(RULES)


def test_unsafe_member_names_are_reported(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "unsafe.odt")
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("../escape.txt", b"x")
    assert "PKG007" in ids(audit_odf(source))


def test_unreadable_source_is_a_finding_not_an_exception(tmp_path: Path) -> None:
    source = tmp_path / "broken.odt"
    source.write_bytes(b"not a zip")
    assert ids(audit_odf(source)) == {"PKG000"}
    assert ids(audit_odf(tmp_path / "missing.odt")) == {"PKG000"}


def test_schema_audit_records_version_and_violations(tmp_path: Path) -> None:
    report = audit_odf(make_minimal_odt(tmp_path / "ok.odt"), schema=True)
    assert report.facts[FactKeys.SCHEMA_VERSION] == "1.4"
    assert report.facts[FactKeys.SCHEMA_VIOLATION_COUNT] == 0
    assert "SCHEMA001" not in ids(report)


def test_schema_audit_rejects_malformed_but_renderable_markup(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "bad.odt", features={"with_data_table": True})
    package = PackageStorage(source)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    package.save(tmp_path / "bad2.odt")
    report = audit_odf(tmp_path / "bad2.odt", schema=True)
    finding = next(f for f in report.findings if f.rule_id == "SCHEMA001")
    assert finding.severity is Severity.WARNING
    assert finding.location == Location("content", "content.xml")


def test_schema_audit_reports_unsupported_versions_as_unavailable(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "v.odt", version="1.2")
    report = audit_odf(source, schema=True)
    assert "SCHEMA002" in ids(report)


def test_template_comments_out_every_open_decision(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "t.odt",
        features={
            "with_plain_email": True,
            "with_data_table": True,
            "with_image_without_alt": True,
        },
    )
    text = prepare_plan(source)[1]
    assert text is not None
    assert '[decisions."graphic.alternative"."content/frame[name=Logo]"]' in text
    assert '[decisions."table.headers"."content/table[name=Data]"]' in text
    assert "text.linkify_addresses" in text
    assert "fingerprint = " in text
    assert load_plan(write_plan(tmp_path, text)).decisions == ()


@pytest.mark.parametrize(
    "features",
    [{"with_plain_email": True}, {"with_data_table": True}, {"with_image_without_alt": True}],
)
def test_template_loads_as_an_empty_configuration(tmp_path: Path, features: Features) -> None:
    source = make_minimal_odt(tmp_path / "t.odt", features=features)
    config = tmp_path / "template.toml"
    text = prepare_plan(source)[1]
    assert text is not None
    config.write_text(text, encoding="utf-8")
    assert load_plan(config).decisions == ()


def write_plan(directory: Path, text: str) -> Path:
    """Write a plan fixture.

    Returns
    -------
    Path
        The review file path.

    """
    path = directory / "review.plan.toml"
    path.write_text(text)
    return path
