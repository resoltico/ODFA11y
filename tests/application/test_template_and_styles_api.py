# SPDX-License-Identifier: MPL-2.0
"""Document planning and family capabilities are available without command handlers."""

import tomllib
from pathlib import Path

import pytest

from odfa11y import audit
from odfa11y.audit import plan_blockers, prepare_plan
from odfa11y.families import REGISTRY
from odfa11y.odf import Family
from odfa11y.report import FactKeys, Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from tests.fixtures.documents import make_flat, make_package
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.errors import DocumentRefusal


@pytest.mark.parametrize("layout", ["package", "flat"])
def test_template_api_prepares_loadable_configuration_for_source_layout(
    tmp_path: Path, layout: str
) -> None:
    source = (make_package if layout == "package" else make_flat)(tmp_path, "text")
    report, template = prepare_plan(source)
    assert report.facts[FactKeys.PACKAGE_LAYOUT] == layout
    assert template is not None
    assert set(tomllib.loads(template)) == {"plan", "decisions"}
    assert plan_blockers(report) is None


@pytest.mark.parametrize("missing", [False, True])
def test_template_api_returns_readability_failure_without_preparing_decisions(
    tmp_path: Path, *, missing: bool
) -> None:
    source = tmp_path / "bad.odt"
    if not missing:
        source.write_bytes(b"invalid ODF")
    report, template = prepare_plan(source)
    assert template is None
    blockers = plan_blockers(report)
    assert blockers is not None
    assert [finding.rule_id for finding in blockers.findings] == ["PKG000"]
    assert blockers.sources == (source,)


def test_fixable_errors_leave_template_planning_available(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", title="")
    report, template = prepare_plan(source)
    assert report.error_count > 0
    assert plan_blockers(report) is None
    assert template is not None
    assert '[decisions."document.metadata"]' in template
    assert "META001" in template


def test_blocker_projection_preserves_original_full_report() -> None:
    report = Report(kind=ReportKind.ODF, subject="source.odt")
    report.raise_(rules.META001)
    report.raise_(rules.PKG000)
    before = report.as_dict()
    blockers = plan_blockers(report)
    assert blockers is not None
    assert report.as_dict() == before
    assert [finding.rule_id for finding in blockers.findings] == ["PKG000"]
    blockers.findings.clear()
    assert report.as_dict() == before


def test_planning_refuses_a_family_without_a_registered_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", title="")
    monkeypatch.delitem(REGISTRY, Family.TEXT)
    report = audit(source).reports[0]
    assert not report.decisions
    with pytest.raises(DocumentRefusal, match="No supported source family"):
        prepare_plan(source)


def test_style_usage_api_reports_text_family_usage(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    rows = audit(source).reports[0].facts[FactKeys.TEXT_PARAGRAPH_STYLES]
    body = next(row for row in rows if row["style"] == "Body")
    count = body["count"]
    assert isinstance(count, int)
    assert count > 0
    assert isinstance(body["spacing"], dict)


@pytest.mark.parametrize("layout", ["package", "flat"])
def test_style_usage_api_rejects_unsupported_family(tmp_path: Path, layout: str) -> None:
    source = (make_package if layout == "package" else make_flat)(tmp_path, "spreadsheet")
    assert FactKeys.TEXT_PARAGRAPH_STYLES not in audit(source).reports[0].facts


def test_unavailable_family_does_not_produce_an_empty_supported_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(REGISTRY, Family.TEXT)
    source = make_minimal_odt(tmp_path / "source.odt")
    with pytest.raises(DocumentRefusal, match="No supported source family"):
        prepare_plan(source)
