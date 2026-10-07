# SPDX-License-Identifier: MPL-2.0
"""Evidence bundles: atomic publication, verifiable manifests and honest review sheets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from odfa11y.errors import OutputError
from odfa11y.evidence import (
    HUMAN_REVIEW_ITEMS,
    check_bundle,
    render_review,
    require_free_directory,
    write_bundle,
)


def record(**changes: object) -> dict[str, Any]:
    """Build a minimal run record.

    Returns
    -------
    dict[str, Any]
        A record shaped like the pipeline's.

    """
    base: dict[str, Any] = {
        "input": {"name": "doc.odt", "sha256": "0" * 64},
        "status": "passed",
        "failed_stage": None,
        "stages": [
            {
                "name": "audit-pdf",
                "status": "passed",
                "reason": None,
                "report": {
                    "summary": {"errors": 0, "warnings": 1},
                    "metadata": {"pages": 2},
                    "findings": [
                        {"severity": "warning", "rule_id": "PDF005", "message": "No title display."}
                    ],
                },
                "remediation": None,
            },
            {"name": "verapdf", "status": "skipped", "reason": "not requested", "report": None},
        ],
    }
    return base | changes


def test_bundle_contains_artifacts_record_review_and_a_verifying_manifest(tmp_path: Path) -> None:
    artifact = tmp_path / "x.bin"
    artifact.write_bytes(b"data")
    target = tmp_path / "bundle"
    write_bundle(target, record(), {"nested/x.bin": artifact})
    assert {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()} == {
        "nested/x.bin",
        "run.json",
        "REVIEW.md",
        "manifest.json",
    }
    assert json.loads((target / "run.json").read_text())["status"] == "passed"
    assert check_bundle(target) == []
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".bundle")]


def test_tampering_removal_and_additions_are_detected(tmp_path: Path) -> None:
    artifact = tmp_path / "x.bin"
    artifact.write_bytes(b"data")
    target = tmp_path / "bundle"
    write_bundle(target, record(), {"x.bin": artifact})
    (target / "x.bin").write_bytes(b"changed")
    (target / "extra.txt").write_text("surprise")
    (target / "REVIEW.md").unlink()
    assert check_bundle(target) == ["Missing: REVIEW.md", "Modified: x.bin", "Unlisted: extra.txt"]


def test_an_unreadable_manifest_is_reported(tmp_path: Path) -> None:
    assert check_bundle(tmp_path)[0].startswith("Cannot read manifest.json")
    (tmp_path / "manifest.json").write_text("{}")
    assert check_bundle(tmp_path)[0].startswith("Cannot read manifest.json")


def test_occupied_directories_are_refused_but_empty_ones_are_reused(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    target.mkdir()
    require_free_directory(target)
    write_bundle(target, record(), {})
    with pytest.raises(OutputError):
        write_bundle(target, record(), {})
    file_path = tmp_path / "file"
    file_path.write_text("x")
    with pytest.raises(OutputError):
        require_free_directory(file_path)


def test_failed_publication_leaves_no_partial_bundle(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    with pytest.raises(FileNotFoundError):
        write_bundle(target, record(), {"x": tmp_path / "missing"})
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_review_separates_facts_from_decisions_and_never_overclaims() -> None:
    text = render_review(record())
    assert "## Machine-established facts" in text
    assert "- `audit-pdf` pages: 2" in text
    assert "PDF005: No title display." in text
    assert "not PDF/UA validation" in text
    for _key, item in HUMAN_REVIEW_ITEMS:
        assert f"- [ ] {item}" in text


def test_review_omits_the_validation_caveat_only_when_verapdf_passed() -> None:
    passed = record()
    passed["stages"][1] = {"name": "verapdf", "status": "passed", "reason": None, "report": None}
    assert "not PDF/UA validation" not in render_review(passed)
    failed = record(status="failed", failed_stage="fidelity")
    assert "(failed at `fidelity`)" in render_review(failed)


def test_review_items_appear_in_the_accessibility_guide() -> None:
    guide = (
        (Path(__file__).parents[1] / "docs/ACCESSIBILITY.md").read_text(encoding="utf-8").lower()
    )
    for key, _item in HUMAN_REVIEW_ITEMS:
        assert key in guide


def test_review_table_cells_stay_on_one_line_and_escape_pipes() -> None:
    failed = record(status="failed", failed_stage="remediate")
    failed["stages"][0]["reason"] = "Remediation failed:\n- set_alt_text [Logo]: a | b"
    table = [
        line for line in render_review(failed).splitlines() if line.startswith("| `audit-pdf`")
    ]
    assert len(table) == 1
    assert "a \\| b" in table[0]
    assert "\n" not in table[0]
