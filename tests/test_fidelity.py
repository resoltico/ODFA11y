# SPDX-License-Identifier: MPL-2.0
"""Fidelity comparison: each kind of difference fails with the right rule; equal renders pass."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.fidelity import compare as comparison

from .pdf_fixtures import text_pdf

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report

LINES = ["Heading line", "A paragraph of body text on the page.", "Another line of text."]


def compare(
    tmp_path: Path, source: Path, candidate: Path, policy: FidelityPolicy | None = None
) -> Report:
    """Compare two PDFs under a policy.

    Returns
    -------
    Report
        The fidelity report.

    """
    return compare_pdfs(source, candidate, policy or FidelityPolicy(), diff_dir=tmp_path / "diff")


def ids(report: Report) -> set[str]:
    """Collect rule identifiers.

    Returns
    -------
    set[str]
        The rule identifiers present.

    """
    return {finding.rule_id for finding in report.findings}


def test_identical_documents_pass_with_zero_difference(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES])
    right = text_pdf(tmp_path / "b.pdf", [LINES])
    report = compare(tmp_path, left, right)
    assert report.findings == []
    assert report.metadata["raster_max_changed_ratio"] == 0.0
    assert not (tmp_path / "diff").exists()


def test_changed_text_is_located_precisely(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES])
    right = text_pdf(
        tmp_path / "b.pdf", [[LINES[0], "A paragraph of BODY text on the page.", LINES[2]]]
    )
    finding = next(f for f in compare(tmp_path, left, right).findings if f.rule_id == "FID003")
    assert "body" in finding.details["source"]
    assert "BODY" in finding.details["candidate"]


def test_a_layout_shift_with_identical_text_fails_the_raster_gate(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], top=180)
    right = text_pdf(tmp_path / "b.pdf", [LINES], top=140)
    report = compare(tmp_path, left, right)
    assert ids(report) == {"FID005"}
    finding = report.findings[0]
    assert finding.details["page"] == 1
    assert finding.details["changed_ratio"] > FidelityPolicy().raster_tolerance
    assert (tmp_path / "diff" / finding.details["diff_image"]).is_file()


def test_a_loose_tolerance_accepts_a_shift_and_a_tight_one_rejects_tiny_changes(
    tmp_path: Path,
) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], top=180)
    right = text_pdf(tmp_path / "b.pdf", [LINES], top=140)
    assert compare(tmp_path, left, right, FidelityPolicy(raster_tolerance=5.0)).findings == []
    nudged = text_pdf(tmp_path / "c.pdf", [LINES], top=179)
    assert "FID005" in ids(compare(tmp_path, left, nudged, FidelityPolicy(raster_tolerance=0.0)))


def test_page_count_and_size_differences_are_reported_when_pagination_must_match(
    tmp_path: Path,
) -> None:
    one = text_pdf(tmp_path / "one.pdf", [LINES])
    two = text_pdf(tmp_path / "two.pdf", [LINES, ["Second page"]])
    assert "FID001" in ids(compare(tmp_path, one, two))
    wide = text_pdf(tmp_path / "wide.pdf", [LINES], size=(300, 200))
    assert "FID002" in ids(compare(tmp_path, one, wide))


def test_may_change_pagination_skips_page_and_raster_checks_but_still_gates_text(
    tmp_path: Path,
) -> None:
    one = text_pdf(tmp_path / "one.pdf", [["First part."]])
    split = text_pdf(tmp_path / "split.pdf", [["First part."], [""]])
    assert compare(tmp_path, one, split, FidelityPolicy(pagination="may-change")).findings == []
    shifted = text_pdf(tmp_path / "shifted.pdf", [["First part."]], top=100)
    assert compare(tmp_path, one, shifted, FidelityPolicy(pagination="may-change")).findings == []
    other = text_pdf(tmp_path / "other.pdf", [["Other part."]])
    assert ids(compare(tmp_path, one, other, FidelityPolicy(pagination="may-change"))) == {"FID003"}


def test_lost_links_fail_and_added_links_are_informational(tmp_path: Path) -> None:
    with_link = text_pdf(tmp_path / "a.pdf", [LINES], links=["https://example.test/a"])
    without = text_pdf(tmp_path / "b.pdf", [LINES])
    assert "FID004" in ids(compare(tmp_path, with_link, without))
    added = compare(tmp_path, without, with_link, FidelityPolicy(raster_tolerance=1.0))
    assert ids(added) == {"FID006"}
    assert added.error_count == 0


def test_changed_link_targets_count_as_lost(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], links=["https://example.test/a"])
    right = text_pdf(tmp_path / "b.pdf", [LINES], links=["https://example.test/b"])
    report = compare(tmp_path, left, right, FidelityPolicy(raster_tolerance=1.0))
    assert ids(report) == {"FID004", "FID006"}


def test_oversized_pages_are_not_rendered(tmp_path: Path) -> None:
    huge = text_pdf(tmp_path / "huge.pdf", [LINES], size=(14400, 14400))
    report = compare(tmp_path, huge, huge)
    assert ids(report) == {"FID007"}


def test_unreadable_pdfs_raise_a_tool_error(tmp_path: Path) -> None:
    good = text_pdf(tmp_path / "a.pdf", [LINES])
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ToolFailedError):
        compare(tmp_path, good, bad)


def test_enormous_dpi_is_controlled_before_float_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = text_pdf(tmp_path / "dpi.pdf", [LINES])
    before = pdf.read_bytes()
    rendered = []
    monkeypatch.setattr(comparison, "_render_ratios", lambda *args: rendered.append(args))
    with pytest.raises(ToolFailedError, match="DPI exceeds the numeric range"):
        compare_pdfs(pdf, pdf, FidelityPolicy(dpi=10**400), diff_dir=tmp_path / "diff")
    assert not rendered
    assert not (tmp_path / "diff").exists()
    assert pdf.read_bytes() == before


@pytest.mark.parametrize("dpi", [72, 144, 4096])
def test_legitimate_dpi_uses_existing_pixel_budget(tmp_path: Path, dpi: int) -> None:
    pdf = text_pdf(tmp_path / "dpi.pdf", [LINES])
    report = compare_pdfs(pdf, pdf, FidelityPolicy(dpi=dpi))
    assert ids(report) == ({"FID007"} if dpi == 4096 else set())
