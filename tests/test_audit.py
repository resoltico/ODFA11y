# SPDX-License-Identifier: MPL-2.0
"""Report accessibility findings for synthetic ODT documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.audit import audit_odt
from odfa11y.report import Severity

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import AuditReport


def ids(report: AuditReport) -> set[str]:
    """Collect the rule identifiers emitted by an audit.

    Returns
    -------
    set[str]
        The emitted rule identifiers.

    """
    return {issue.rule_id for issue in report.issues}


def test_minimal_document_passes_core_audit(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "ok.odt")
    report = audit_odt(source)
    assert report.error_count == 0


def test_audit_detects_wrong_version(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "old.odt", version="1.3")
    report = audit_odt(source)
    assert "ODF001" in ids(report)
    assert report.error_count >= len(("content.xml", "styles.xml", "meta.xml", "manifest"))


def test_audit_detects_plain_email_and_data_table_header(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "issues.odt",
        with_plain_email=True,
        with_data_table=True,
        with_table_header=False,
    )
    report = audit_odt(source)
    assert "LNK001" in ids(report)
    assert "TBL002" in ids(report)


def test_audit_detects_missing_graphic_alt_text(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "image.odt", with_image_without_alt=True)
    report = audit_odt(source)
    assert "IMG001" in ids(report)
    assert any(i.severity is Severity.ERROR for i in report.issues if i.rule_id == "IMG001")
