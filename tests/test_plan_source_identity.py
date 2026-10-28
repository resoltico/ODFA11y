# SPDX-License-Identifier: MPL-2.0
"""Binding verifies the same private input bytes that were audited and edited."""

from __future__ import annotations

import hashlib
import importlib
import tomllib
from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest

from odfa11y.audit import prepare_plan
from odfa11y.errors import PlanError
from odfa11y.plans import Plan, parse_tables, registered_kinds
from odfa11y.remediation import remediate

from .documents import Variant, make_flat
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def test_remediation_refuses_unreviewed_loaded_bytes_after_source_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = make_minimal_odt(tmp_path / "reviewed.odt")
    reviewed_bytes = reviewed.read_bytes()
    source = make_flat(
        tmp_path, "text", Variant(body="<office:text><text:p>Unreviewed</text:p></office:text>")
    )
    plan = Plan.for_source(reviewed)
    module = importlib.import_module("odfa11y.remediation.apply")
    original = module._document  # noqa: SLF001  Inject a source exchange at the actual model-load boundary.

    def exchange(path: Path, destination: Path) -> OdfDocument:
        document = original(path, destination)
        source.write_bytes(reviewed_bytes)
        return document

    monkeypatch.setattr(module, "_document", exchange)
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
    original = module.audit_odf

    def exchange(path: Path) -> Report:
        report = original(path)
        source.write_bytes(replacement_bytes)
        return report

    monkeypatch.setattr(module, "audit_odf", exchange)
    report, text = prepare_plan(source)
    assert text is not None
    assert report.subject == str(source)
    assert report.sources == (source,)
    plan = parse_tables(tomllib.loads(text), registered_kinds())
    assert plan.header.source.sha256 == hashlib.sha256(audited_bytes).hexdigest()
    assert any(f.rule_id == "META001" for f in report.findings)
    with pytest.raises(PlanError, match="digest mismatch"):
        remediate(source, tmp_path / "out.odt", plan)
    assert source.read_bytes() == replacement_bytes
