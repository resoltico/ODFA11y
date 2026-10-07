# SPDX-License-Identifier: MPL-2.0
"""Report accessibility findings for synthetic ODT documents."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf, render_template
from odfa11y.config import load_config
from odfa11y.families.text import ADAPTER
from odfa11y.odf import PackageStorage
from odfa11y.report import RULES, Location, Severity

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report

    from .fixtures import Features


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
    assert report.metadata["odf_version"] == "1.4"


def test_older_consistent_version_is_reported_not_rejected(tmp_path: Path) -> None:
    report = audit_odf(make_minimal_odt(tmp_path / "old.odt", version="1.3"))
    assert report.error_count == 0
    assert report.metadata["odf_version"] == "1.3"


def test_members_declaring_different_versions_are_an_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "mixed.odt")
    package = PackageStorage(source)
    package.write_member("meta.xml", package.read("meta.xml").replace(b'"1.4"', b'"1.3"'))
    package.save(tmp_path / "mixed2.odt")
    assert "ODF001" in ids(audit_odf(tmp_path / "mixed2.odt"))


def test_audit_detects_plain_email_and_data_table_header(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "issues.odt", with_plain_email=True, with_data_table=True)
    report = audit_odf(source)
    assert {"TXT030", "TXT021"} <= ids(report)
    table = next(f for f in report.findings if f.rule_id == "TXT021")
    assert table.details["table"] == "Data"
    assert table.remedy == "text.table_headers"


def test_audit_detects_missing_graphic_alt_text(tmp_path: Path) -> None:
    report = audit_odf(make_minimal_odt(tmp_path / "image.odt", with_image_without_alt=True))
    finding = next(f for f in report.findings if f.rule_id == "TXT010")
    assert finding.severity is Severity.ERROR
    assert finding.details["frame"] == "Logo"
    assert finding.remedy == "text.alt_text"


def test_every_emitted_rule_is_registered(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "all.odt",
        with_plain_email=True,
        with_data_table=True,
        with_image_without_alt=True,
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
    assert report.metadata["schema_version"] == "1.4"
    assert report.metadata["schema_violations"] == 0
    assert "ODF900" not in ids(report)


def test_schema_audit_rejects_malformed_but_renderable_markup(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "bad.odt", with_data_table=True)
    package = PackageStorage(source)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    package.save(tmp_path / "bad2.odt")
    report = audit_odf(tmp_path / "bad2.odt", schema=True)
    finding = next(f for f in report.findings if f.rule_id == "ODF900")
    assert finding.severity is Severity.WARNING
    assert finding.location == Location("content", "content.xml")


def test_schema_audit_reports_unsupported_versions_as_unavailable(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "v.odt", version="1.2")
    report = audit_odf(source, schema=True)
    assert "ODF905" in ids(report)


def test_template_comments_out_every_open_decision(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "t.odt", with_plain_email=True, with_data_table=True, with_image_without_alt=True
    )
    text = render_template(audit_odf(source), ADAPTER)
    assert '[text.alt_text."Logo"]' in text
    assert '"Data" = { rows = 1, fingerprint = ' in text
    assert "linkify_plain_addresses" in text
    assert "fingerprint = " in text
    assert all(line.startswith("#") or not line.strip() for line in text.splitlines())


@pytest.mark.parametrize(
    "features",
    [{"with_plain_email": True}, {"with_data_table": True}, {"with_image_without_alt": True}],
)
def test_template_loads_as_an_empty_configuration(tmp_path: Path, features: Features) -> None:
    source = make_minimal_odt(tmp_path / "t.odt", **features)
    config = tmp_path / "template.toml"
    config.write_text(render_template(audit_odf(source), ADAPTER), encoding="utf-8")
    assert load_config(config).operations == ()
