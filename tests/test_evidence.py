# SPDX-License-Identifier: MPL-2.0
"""Evidence bundles: atomic publication, safe verification, path hygiene, honest review sheets."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from odfa11y.errors import OutputError
from odfa11y.evidence import (
    Redactor,
    check_bundle,
    render_review,
    require_free_directory,
    write_bundle,
)
from odfa11y.families.text import ADAPTER

REVIEW_ITEMS = [{"key": item.key, "text": item.text} for item in ADAPTER.review_items]
NO_REDACTION = Redactor(())


def record(**changes: object) -> dict[str, Any]:
    """Build a minimal run record.

    Returns
    -------
    dict[str, Any]
        A record shaped like the pipeline's.

    """
    base: dict[str, Any] = {
        "document": {"name": "doc.odt", "sha256": "0" * 64},
        "status": "passed",
        "failed_stage": None,
        "human_review": REVIEW_ITEMS,
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


def test_bundle_contains_artifacts_record_review_and_a_verifying_manifest(tmp_path: Path) -> None:
    target = bundle(tmp_path, {"nested/x.bin": b"data"})
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
    target = bundle(tmp_path, {"x.bin": b"data"})
    (target / "x.bin").write_bytes(b"changed")
    (target / "extra.txt").write_text("surprise")
    (target / "REVIEW.md").unlink()
    assert check_bundle(target) == ["Missing: REVIEW.md", "Modified: x.bin", "Unlisted: extra.txt"]


def test_an_unreadable_or_malformed_manifest_is_reported(tmp_path: Path) -> None:
    assert check_bundle(tmp_path)[0].startswith("Cannot read manifest.json")
    for text in ("{}", "[]", '{"format": 1}', '{"format": 2, "files": {}}', "not json"):
        (tmp_path / "manifest.json").write_text(text)
        assert check_bundle(tmp_path)[0].startswith("Cannot read manifest.json"), text


@pytest.mark.parametrize(
    "name",
    [
        "/etc/passwd",
        "../outside",
        "a/../../outside",
        "a//b",
        "./a",
        "a/",
        "C:/Windows/win.ini",
        "a\\b",
        "a\x00b",
        "manifest.json",
        "",
    ],
)
def test_a_manifest_naming_an_unsafe_path_is_rejected_before_any_read(
    tmp_path: Path, name: str
) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("outside the bundle")
    directory = tmp_path / "bundle"
    directory.mkdir()
    digest = "0" * 64
    (directory / "manifest.json").write_text(json.dumps({"format": 1, "files": {name: digest}}))
    (directory / "x").write_text("x")
    problems = check_bundle(directory)
    assert problems
    assert any("unsafe name" in problem or "empty name" in problem for problem in problems)


def test_a_manifest_with_a_bad_digest_or_duplicate_keys_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"format": 1, "files": {"a": "xyz"}}')
    assert "invalid digest" in check_bundle(tmp_path)[0]
    digest = "0" * 64
    (tmp_path / "manifest.json").write_text(
        f'{{"format": 1, "files": {{"a": "{digest}", "a": "{digest}"}}}}'
    )
    assert "duplicate key" in check_bundle(tmp_path)[0]


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_symbolic_links_are_never_followed_or_trusted(tmp_path: Path) -> None:
    target = bundle(tmp_path, {"real.bin": b"data"})
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"data")
    (target / "link.bin").symlink_to(outside)
    (target / "linkdir").symlink_to(tmp_path, target_is_directory=True)
    problems = check_bundle(target)
    assert any("Unsafe: link.bin" in problem for problem in problems)
    assert any("Unsafe: linkdir" in problem for problem in problems)
    # A manifest entry that passes through a link is refused, not read.
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["files"]["linkdir/outside.bin"] = "0" * 64
    (target / "manifest.json").write_text(json.dumps(manifest))
    assert any("passes through a symbolic link" in p for p in check_bundle(target))


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_a_listed_file_replaced_by_a_link_is_reported(tmp_path: Path) -> None:
    target = bundle(tmp_path, {"x.bin": b"data"})
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"data")
    (target / "x.bin").unlink()
    (target / "x.bin").symlink_to(outside)
    assert any("Unsafe: x.bin" in problem for problem in check_bundle(target))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_special_files_are_reported_without_being_opened(tmp_path: Path) -> None:
    target = bundle(tmp_path)
    os.mkfifo(target / "pipe")
    assert any("Unsafe: pipe" in problem for problem in check_bundle(target))


def test_only_the_root_manifest_is_exempt_from_the_inventory(tmp_path: Path) -> None:
    target = bundle(tmp_path, {"x.bin": b"data"})
    (target / "nested").mkdir()
    (target / "nested" / "manifest.json").write_text("{}")
    assert "Unlisted: nested/manifest.json" in check_bundle(target)


def test_the_writer_rejects_names_the_verifier_would_reject(tmp_path: Path) -> None:
    source = tmp_path / "s.bin"
    source.write_bytes(b"x")
    for name in ("../escape", "/abs", "a//b", "manifest.json"):
        with pytest.raises(OutputError, match="Unsafe bundle file name"):
            write_bundle(tmp_path / "bundle", record(), {name: source}, NO_REDACTION)
    assert not (tmp_path / "bundle").exists()


def test_nested_manifest_artifacts_are_inventoried_not_exempted(tmp_path: Path) -> None:
    target = bundle(tmp_path, {"sub/manifest.json": b"{}"})
    assert "sub/manifest.json" in json.loads((target / "manifest.json").read_text())["files"]
    assert check_bundle(target) == []


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


def test_redaction_replaces_known_locations_and_any_remaining_absolute_path(
    tmp_path: Path,
) -> None:
    work = tmp_path / "work-dir"
    redactor = Redactor.for_locations({"work": work})
    cleaned = redactor.record({
        "reason": f"failed at {work}/remediated.odt and /somewhere/else/file.pdf",
        "nested": [f"{work.as_uri()}/x", "C:\\Users\\someone\\doc.odt", "/Link", "https://h/a/b"],
    })
    flat = json.dumps(cleaned)
    assert str(work) not in flat
    assert "<work>/remediated.odt" in flat
    assert "<path>/file.pdf" in flat
    assert "<path>/doc.odt" in flat
    assert "/somewhere" not in flat
    assert "Users" not in flat
    assert "/Link" in flat
    assert "https://h/a/b" in flat


def test_text_artifacts_are_redacted_and_binary_ones_are_not(tmp_path: Path) -> None:
    work = tmp_path / "scratch"
    work.mkdir()
    xml = tmp_path / "report.xml"
    xml.write_text(f"<name>{work}/remediated.pdf</name>", encoding="utf-8")
    binary = tmp_path / "data.bin"
    binary.write_bytes(str(work).encode())
    redactor = Redactor.for_locations({"work": work})
    target = tmp_path / "bundle"
    write_bundle(target, record(), {"report.xml": xml, "data.bin": binary}, redactor)
    assert (target / "report.xml").read_text() == "<name><work>/remediated.pdf</name>"
    assert (target / "data.bin").read_bytes() == str(work).encode()
    assert check_bundle(target) == []


def test_review_separates_facts_from_decisions_and_never_overclaims() -> None:
    text = render_review(record())
    assert "## Machine-established facts" in text
    assert "- `audit-pdf` pages: 2" in text
    assert "PDF005: No title display." in text
    assert "not PDF/UA validation" in text
    for item in REVIEW_ITEMS:
        assert f"- [ ] {item['text']}" in text


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
    for item in REVIEW_ITEMS:
        assert item["key"] in guide


def test_review_table_cells_stay_on_one_line_and_escape_pipes() -> None:
    failed = record(status="failed", failed_stage="remediate")
    failed["stages"][0]["reason"] = "Remediation failed:\n- set_alt_text [Logo]: a | b"
    table = [
        line for line in render_review(failed).splitlines() if line.startswith("| `audit-pdf`")
    ]
    assert len(table) == 1
    assert "a \\| b" in table[0]
    assert "\n" not in table[0]
