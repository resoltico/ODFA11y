# SPDX-License-Identifier: MPL-2.0
"""Fidelity comparison: each kind of difference fails with the right rule; equal renders pass."""

from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.application.native import NativeTools
from odfa11y.errors import ToolFailure
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
from odfa11y.report import FactKeys
from tests.fixtures.native import refusing
from tests.fixtures.pdf import text_pdf
lazy from odfa11y.report import Report

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
    return compare_pdfs(source, candidate, policy or Pagination.SAME(), diff_dir=tmp_path / "diff")


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
    assert report.facts[FactKeys.FIDELITY_RASTER_MAX_CHANGED_RATIO] == 0.0
    assert not (tmp_path / "diff").exists()


def test_changed_text_is_located_precisely(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES])
    right = text_pdf(
        tmp_path / "b.pdf", [[LINES[0], "A paragraph of BODY text on the page.", LINES[2]]]
    )
    finding = next(f for f in compare(tmp_path, left, right).findings if f.rule_id == "FID003")
    source_text, candidate_text = finding.details["source"], finding.details["candidate"]
    assert isinstance(source_text, str)
    assert isinstance(candidate_text, str)
    assert "body" in source_text
    assert "BODY" in candidate_text


def test_a_layout_shift_with_identical_text_fails_the_raster_gate(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], top=180)
    right = text_pdf(tmp_path / "b.pdf", [LINES], top=140)
    report = compare(tmp_path, left, right)
    assert ids(report) == {"FID005"}
    finding = report.findings[0]
    assert finding.details["page"] == 1
    changed_ratio, diff_image = finding.details["changed_ratio"], finding.details["diff_image"]
    assert isinstance(changed_ratio, float)
    assert isinstance(diff_image, str)
    assert changed_ratio > Pagination.SAME().raster_tolerance
    assert (tmp_path / "diff" / diff_image).is_file()


def test_a_loose_tolerance_accepts_a_shift_and_a_tight_one_rejects_tiny_changes(
    tmp_path: Path,
) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], top=180)
    right = text_pdf(tmp_path / "b.pdf", [LINES], top=140)
    assert compare(tmp_path, left, right, Pagination.SAME(raster_tolerance=5.0)).findings == []
    nudged = text_pdf(tmp_path / "c.pdf", [LINES], top=179)
    assert "FID005" in ids(compare(tmp_path, left, nudged, Pagination.SAME(raster_tolerance=0.0)))


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
    assert compare(tmp_path, one, split, Pagination.MAY_CHANGE).findings == []
    shifted = text_pdf(tmp_path / "shifted.pdf", [["First part."]], top=100)
    assert compare(tmp_path, one, shifted, Pagination.MAY_CHANGE).findings == []
    other = text_pdf(tmp_path / "other.pdf", [["Other part."]])
    assert ids(compare(tmp_path, one, other, Pagination.MAY_CHANGE)) == {"FID003"}


def test_lost_links_fail_and_added_links_are_informational(tmp_path: Path) -> None:
    with_link = text_pdf(tmp_path / "a.pdf", [LINES], links=["https://example.test/a"])
    without = text_pdf(tmp_path / "b.pdf", [LINES])
    assert "FID004" in ids(compare(tmp_path, with_link, without))
    added = compare(tmp_path, without, with_link, Pagination.SAME(raster_tolerance=1.0))
    assert ids(added) == {"FID006"}
    assert added.error_count == 0


def test_changed_link_targets_count_as_lost(tmp_path: Path) -> None:
    left = text_pdf(tmp_path / "a.pdf", [LINES], links=["https://example.test/a"])
    right = text_pdf(tmp_path / "b.pdf", [LINES], links=["https://example.test/b"])
    report = compare(tmp_path, left, right, Pagination.SAME(raster_tolerance=1.0))
    assert ids(report) == {"FID004", "FID006"}


def test_oversized_pages_are_not_rendered(tmp_path: Path) -> None:
    huge = text_pdf(tmp_path / "huge.pdf", [LINES], size=(14400, 14400))
    report = compare(tmp_path, huge, huge)
    assert ids(report) == {"FID007"}


def test_unreadable_pdfs_raise_a_tool_error(tmp_path: Path) -> None:
    good = text_pdf(tmp_path / "a.pdf", [LINES])
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ToolFailure):
        compare(tmp_path, good, bad)


def test_oversized_page_is_controlled_before_rendering(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = text_pdf(tmp_path / "large.pdf", [LINES], size=(5000, 5000))
    before = pdf.read_bytes()
    rendered = []
    native_tools = replace(native_tools, render=refusing(rendered))
    report = compare_pdfs(
        pdf, pdf, Pagination.SAME(), diff_dir=tmp_path / "diff", render=native_tools.render
    )
    assert ids(report) == {"FID007"}
    assert not rendered
    assert not (tmp_path / "diff").exists()
    assert pdf.read_bytes() == before


@pytest.mark.parametrize("width", [200, 512, 5000])
def test_fixed_resolution_retains_the_existing_pixel_limit(tmp_path: Path, width: int) -> None:
    pdf = text_pdf(tmp_path / "sized.pdf", [LINES], size=(width, width))
    report = compare_pdfs(pdf, pdf, Pagination.SAME())
    assert ids(report) == ({"FID007"} if width == 5000 else set())
