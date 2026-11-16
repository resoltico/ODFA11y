# SPDX-License-Identifier: MPL-2.0
"""Ambiguous and unsafe ZIP names never establish a native or editing package view."""

import zipfile
from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y import audit
from odfa11y.application.native import NativeTools
from odfa11y.audit import audit_odf, prepare_plan
from odfa11y.errors import PackageError
from odfa11y.families.text.audit import TextStyleMeasurements
from odfa11y.odf import OdfDocument, PackageStorage
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.native import export_document
from odfa11y.run.profiles import profile_named
from tests.fixtures.answers import metadata_input
from tests.fixtures.operations import apply_answers
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt
from tests.odf.test_package_protection import encrypted_manifest


@pytest.mark.parametrize(
    "member", ["META-INF/manifest.xml", "content.xml", "styles.xml", "opaque.bin"]
)
@pytest.mark.parametrize("order", ["ambiguous-first", "ambiguous-last"])
def test_duplicate_members_refuse_every_guard_before_kind_or_native_access(
    native_tools: NativeTools,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member: str,
    order: str,
) -> None:
    original = make_minimal_odt(tmp_path / "original.odt")
    storage = PackageStorage(original)
    first = (
        encrypted_manifest(storage, "content.xml", "encryption-data")
        if member == "META-INF/manifest.xml"
        else b"unestablished bytes"
    )
    source = tmp_path / "duplicate.odt"
    with zipfile.ZipFile(source, "w") as archive:
        for name in storage.order:
            if name != member:
                archive.writestr(name, storage.read(name))
        pair = [first, storage.read(member) if storage.has(member) else b"opaque bytes"]
        if order == "ambiguous-last":
            pair.reverse()
        archive.writestr(member, pair[0])
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr(member, pair[1])
    _assert_guarded_refusal(native_tools, source, tmp_path, monkeypatch, rules.PKG009.id)


def test_unsafe_member_names_refuse_before_kind_or_native_access(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "unsafe.odt")
    storage = PackageStorage(source)
    # Build this source directly: low-level saves deliberately refuse unsafe output names.
    with zipfile.ZipFile(source, "w") as archive:
        for name in storage.order:
            archive.writestr(name, storage.read(name))
        archive.writestr("../outside.xml", b"unestablished bytes")
    _assert_guarded_refusal(native_tools, source, tmp_path, monkeypatch, rules.PKG010.id)


def _assert_guarded_refusal(
    native_tools: NativeTools,
    source: Path,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule: str,
) -> None:
    before = source.read_bytes()
    protection = OdfDocument.open(source).protection
    assert protection.inspection_blocked
    assert protection.ambiguous_members or protection.unsafe_members

    def forbidden_kind(_document: OdfDocument) -> None:
        pytest.fail("Unestablished package names reached body/kind inspection")

    def forbidden_native(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unestablished package names reached native processing")

    monkeypatch.setattr(OdfDocument, "kind", property(forbidden_kind))
    monkeypatch.setattr(OdfDocument, "detection", property(forbidden_kind))
    native_tools = replace(native_tools, export=forbidden_native)
    report = audit_odf(source)
    assert [finding.rule_id for finding in report.findings] == [rule]
    assert "complete inspection" in report.findings[0].message
    assert not report.facts
    planned, template = prepare_plan(source)
    assert [finding.rule_id for finding in planned.findings] == [rule]
    assert template is None
    destination = directory / "existing.odt"
    destination.write_bytes(b"existing output")
    for operations in ([], [metadata_input(title="Reviewed")]):
        for dry_run in (False, True):
            with pytest.raises(PackageError, match=r"ambiguous|malformed"):
                apply_answers(source, destination, operations, dry_run=dry_run)
    pdf = directory / "existing.pdf"
    pdf.write_bytes(b"existing PDF")
    with pytest.raises(PackageError, match=r"ambiguous|unsafe"):
        export_document(source, pdf, native_tools=native_tools)
    style_report = audit(source).reports[0]
    assert style_report.error_count > 0
    assert not any(isinstance(record, TextStyleMeasurements) for record in style_report.facts)
    record = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        directory / "evidence",
        RunSettings(profile=profile_named("source")),
        native_tools=native_tools,
    )
    assert record.failed_stage == "audit-source"
    assert record.exit_status == 2
    assert not (directory / "evidence" / "remediated.odt").exists()
    assert source.read_bytes() == before
    assert destination.read_bytes() == b"existing output"
    assert pdf.read_bytes() == b"existing PDF"
