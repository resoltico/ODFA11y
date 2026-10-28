# SPDX-License-Identifier: MPL-2.0
"""Document planning and family capabilities are available without command handlers."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import prepare_template, template_blockers
from odfa11y.errors import UnsupportedKindError
from odfa11y.families import REGISTRY, style_usage
from odfa11y.odf import Family
from odfa11y.report import FactKeys, Report, rules

from .documents import make_flat, make_package
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("layout", ["package", "flat"])
def test_template_api_prepares_loadable_configuration_for_source_layout(
    tmp_path: Path, layout: str
) -> None:
    source = (make_package if layout == "package" else make_flat)(tmp_path, "text")
    report, template = prepare_template(source)
    assert report.facts[FactKeys.PACKAGE_LAYOUT] == layout
    assert template is not None
    assert tomllib.loads(template) == {}
    assert template_blockers(report) is None


@pytest.mark.parametrize("missing", [False, True])
def test_template_api_returns_readability_failure_without_preparing_decisions(
    tmp_path: Path, *, missing: bool
) -> None:
    source = tmp_path / "bad.odt"
    if not missing:
        source.write_bytes(b"invalid ODF")
    report, template = prepare_template(source)
    assert template is None
    blockers = template_blockers(report)
    assert blockers is not None
    assert [finding.rule_id for finding in blockers.findings] == ["PKG000"]
    assert blockers.sources == (source,)


def test_fixable_errors_leave_template_planning_available(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", title="")
    report, template = prepare_template(source)
    assert report.error_count > 0
    assert template_blockers(report) is None
    assert template is not None
    assert '# title = ""  # META001' in template


def test_blocker_projection_preserves_original_full_report() -> None:
    report = Report(kind="odf", subject="source.odt")
    report.add(rules.META001)
    report.add(rules.PKG000)
    before = report.as_dict()
    blockers = template_blockers(report)
    assert blockers is not None
    assert report.as_dict() == before
    assert [finding.rule_id for finding in blockers.findings] == ["PKG000"]
    blockers.findings.clear()
    assert report.as_dict() == before


def test_generic_adapter_retains_common_metadata_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", title="")
    monkeypatch.delitem(REGISTRY, Family.TEXT)
    report, template = prepare_template(source)
    assert report.facts[FactKeys.DOCUMENT_ADAPTER] == "generic"
    assert template is not None
    assert '# title = ""  # META001' in template


def test_style_usage_api_reports_text_family_usage(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    rows = style_usage(source)
    body = next(row for row in rows if row["style"] == "Body")
    assert body["count"] > 0
    assert isinstance(body["spacing"], dict)


@pytest.mark.parametrize("layout", ["package", "flat"])
def test_style_usage_api_rejects_unsupported_family(tmp_path: Path, layout: str) -> None:
    source = (make_package if layout == "package" else make_flat)(tmp_path, "spreadsheet")
    with pytest.raises(UnsupportedKindError, match="spreadsheet"):
        style_usage(source)


def test_template_api_without_decisions_still_returns_commented_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(REGISTRY, Family.TEXT)
    source = make_minimal_odt(tmp_path / "source.odt")
    report, template = prepare_template(source)
    assert not any(finding.remedy for finding in report.findings)
    assert template is not None
    assert "no decisions" in template
    assert tomllib.loads(template) == {}
