# SPDX-License-Identifier: AGPL-3.0-only
"""Binding verifies the same private input bytes that were audited and edited."""

import hashlib
import importlib
import tomllib
lazy from pathlib import Path

import pytest

from odfa11y.application.remediate import remediate
from odfa11y.audit import prepare_plan
from odfa11y.errors import PlanError
from odfa11y.plans import Plan, parse_tables
from odfa11y.remediate.catalogue import registered_kinds
from odfa11y.rules import registry as rules
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


def test_remediation_refuses_unreviewed_loaded_bytes_after_source_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = make_minimal_odt(tmp_path / "reviewed.odt")
    reviewed_bytes = reviewed.read_bytes()
    source = make_flat(
        tmp_path, "text", Variant(body="<office:text><text:p>Unreviewed</text:p></office:text>")
    )
    plan = Plan.for_source(reviewed)
    module = importlib.import_module("odfa11y.application.remediate")
    original = module.require_remediable

    def exchange(document: OdfDocument, selected: Path) -> None:
        original(document, selected)
        source.write_bytes(reviewed_bytes)

    monkeypatch.setattr(module, "require_remediable", exchange)
    destination = tmp_path / "out.fodt"
    with pytest.raises(PlanError, match="digest mismatch"):
        remediate(source, destination, plan)
    assert not destination.exists()
    assert source.read_bytes() == reviewed_bytes


def test_plan_header_binds_audited_bytes_when_original_source_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", title="")
    audited_bytes = source.read_bytes()
    replacement = make_minimal_odt(tmp_path / "replacement.odt", title="Different document")
    replacement_bytes = replacement.read_bytes()
    module = importlib.import_module("odfa11y.audit.plan")
    original = module.audit_document
    displayed_source = source

    def exchange(
        document: OdfDocument, *, subject: str, source: Path | None = None, schema: bool = False
    ) -> Report:
        report = original(document, subject=subject, source=source, schema=schema)
        displayed_source.write_bytes(replacement_bytes)
        return report

    monkeypatch.setattr(module, "audit_document", exchange)
    report, text = prepare_plan(source)
    assert text is not None
    assert report.subject == str(source)
    assert report.sources == (source,)
    plan = parse_tables(tomllib.loads(text), registered_kinds())
    assert plan.header.source.sha256 == hashlib.sha256(audited_bytes).hexdigest()
    assert any(f.rule_id == rules.META001.id for f in report.findings)
    with pytest.raises(PlanError, match="digest mismatch"):
        remediate(source, tmp_path / "out.odt", plan)
    assert source.read_bytes() == replacement_bytes


def test_planning_opens_the_captured_document_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    original = OdfDocument.open
    opened = []

    def open_document(path: str | Path) -> OdfDocument:
        opened.append(Path(path))
        return original(path)

    monkeypatch.setattr(OdfDocument, "open", staticmethod(open_document))
    _report, template = prepare_plan(source)
    assert template is not None
    assert len(opened) == 1
    assert opened[0].parent != source.parent
