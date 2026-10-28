# SPDX-License-Identifier: MPL-2.0
"""Evidence bundles: atomic publication, safe verification, path hygiene, honest review sheets."""

from __future__ import annotations

from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.errors import OutputError
from odfa11y.evidence import (
    Redactor,
    render_review,
    require_free_directory,
    write_bundle,
)
from odfa11y.families.text import ADAPTER
from odfa11y.outcomes import StageStatus
from tests.fixtures.paths import REPOSITORY
from tests.fixtures.records import record

REVIEW_ITEMS = ADAPTER.review_items
NO_REDACTION = Redactor(())


def bundle(tmp_path: Path, artifacts: dict[str, bytes] | None = None) -> Path:
    """Write a bundle holding the given artifacts.

    Returns
    -------
    Path
        The published bundle directory.

    """
    sources = {}
    for name, data in (artifacts or {}).items():
        source = tmp_path / f"source-{len(sources)}.bin"
        source.write_bytes(data)
        sources[name] = source
    target = tmp_path / "bundle"
    write_bundle(target, record(), sources, NO_REDACTION)
    return target


def test_occupied_directories_are_refused_but_empty_ones_are_reused(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    target.mkdir()
    require_free_directory(target)
    write_bundle(target, record(), {}, NO_REDACTION)
    with pytest.raises(OutputError):
        write_bundle(target, record(), {}, NO_REDACTION)
    file_path = tmp_path / "file"
    file_path.write_text("x")
    with pytest.raises(OutputError):
        require_free_directory(file_path)


def test_failed_publication_leaves_no_partial_bundle(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    with pytest.raises(FileNotFoundError):
        write_bundle(target, record(), {"x": tmp_path / "missing"}, NO_REDACTION)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_review_separates_facts_from_decisions_and_never_overclaims() -> None:
    text = render_review(record())
    assert "## Machine-established facts" in text
    assert "- `audit-pdf` pdf.page_count: 2" in text
    assert "PDF005: No title display." in text
    assert "not PDF/UA validation" in text
    for item in REVIEW_ITEMS:
        assert f"- [ ] {item.text}" in text


def test_review_omits_the_validation_caveat_only_when_verapdf_passed() -> None:
    passed = record()
    passed.stages[1] = replace(passed.stages[1], status=StageStatus.PASSED)
    assert "not PDF/UA validation" not in render_review(passed)
    failed = record(status="failed", failed_stage="fidelity")
    assert "(failed at `fidelity`)" in render_review(failed)


def test_review_items_appear_in_the_accessibility_guide() -> None:
    guide = (REPOSITORY / "docs/ACCESSIBILITY.md").read_text(encoding="utf-8").lower()
    for item in REVIEW_ITEMS:
        assert item.key in guide


def test_review_table_cells_stay_on_one_line_and_escape_pipes() -> None:
    failed = record(status="failed", failed_stage="remediate")
    failed.stages[0] = replace(
        failed.stages[0], reason="Remediation failed:\n- set_graphic_alternatives [Logo]: a | b"
    )
    table = [
        line for line in render_review(failed).splitlines() if line.startswith("| `audit-pdf`")
    ]
    assert len(table) == 1
    assert "a \\| b" in table[0]
    assert "\n" not in table[0]
