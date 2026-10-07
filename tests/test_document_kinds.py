# SPDX-License-Identifier: MPL-2.0
"""Every ODF kind, in both layouts, is recognised, audited and kept apart from other families."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.families import GENERIC, adapter_for
from odfa11y.odf import KINDS, Family, OdfDocument, validate

from .documents import KIND_SPECS, make_flat, make_package

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report

LAYOUTS = {"package": make_package, "flat": make_flat}
CASES = [(name, layout) for name in KIND_SPECS for layout in LAYOUTS]


def ids(report: Report) -> set[str]:
    return {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize(("name", "layout"), CASES)
def test_every_kind_is_detected_in_both_layouts(tmp_path: Path, name: str, layout: str) -> None:
    spec = KIND_SPECS[name]
    document = OdfDocument.open(LAYOUTS[layout](tmp_path, name))
    assert document.layout == layout
    assert document.kind is not None
    assert document.kind.media_type == spec.media_type
    assert document.kind.family.value == spec.family
    assert document.detection.body_element == document.kind.body_element


@pytest.mark.parametrize(("name", "layout"), CASES)
def test_every_kind_audits_without_errors_and_only_text_has_semantic_rules(
    tmp_path: Path, name: str, layout: str
) -> None:
    report = audit_odf(LAYOUTS[layout](tmp_path, name), schema=True)
    assert report.error_count == 0, [f.as_dict() for f in report.findings]
    assert report.metadata["layout"] == layout
    assert report.metadata["family"] == KIND_SPECS[name].family
    is_text = KIND_SPECS[name].family == "text"
    assert report.metadata["adapter"] == ("text" if is_text else "generic")
    assert ("ODF009" in ids(report)) is (not is_text)
    if not is_text:
        assert not {i for i in ids(report) if i.startswith("TXT")}


@pytest.mark.parametrize(("name", "layout"), [c for c in CASES if KIND_SPECS[c[0]].schema_valid])
def test_synthetic_documents_validate_against_the_bundled_schema(
    tmp_path: Path, name: str, layout: str
) -> None:
    result = validate(OdfDocument.open(LAYOUTS[layout](tmp_path, name)))
    assert result.available
    assert result.violations == {}, result.messages()


def test_the_registry_serves_text_with_its_adapter_and_everything_else_generically() -> None:
    for kind in KINDS.values():
        adapter = adapter_for(kind)
        assert adapter is (adapter_for(kind))
        if kind.family is Family.TEXT:
            assert adapter.name == "text"
        else:
            assert adapter is GENERIC
    assert adapter_for(None) is GENERIC


def test_every_kind_has_its_own_short_name() -> None:
    names = [kind.name for kind in KINDS.values()]
    assert len(names) == len(set(names))
    assert "application" not in " ".join(names)


@pytest.mark.parametrize("damage", [b"\n", b" ", "é".encode()])
def test_a_damaged_mimetype_member_is_reported_and_the_audit_continues(
    tmp_path: Path, damage: bytes
) -> None:
    source = make_package(tmp_path, "text")
    damaged = tmp_path / "damaged.odt"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(damaged, "w") as copy:
        for member in original.infolist():
            data = original.read(member.filename)
            copy.writestr(member, data + damage if member.filename == "mimetype" else data)
    report = audit_odf(damaged)
    assert "PKG001" in {f.rule_id for f in report.findings}
    assert "ODF005" not in {f.rule_id for f in report.findings}
    assert report.metadata["document_kind"] == "text"


def test_a_content_root_that_is_not_document_content_is_an_error(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text")
    wrong = tmp_path / "wrong.odt"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(wrong, "w") as copy:
        for member in original.infolist():
            data = original.read(member.filename)
            copy.writestr(member, b"<foo/>" if member.filename == "content.xml" else data)
    assert "ODF011" in {f.rule_id for f in audit_odf(wrong).findings}
    assert "ODF011" not in {f.rule_id for f in audit_odf(source).findings}
