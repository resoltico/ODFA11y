# SPDX-License-Identifier: MPL-2.0
"""Verifying a bundle treats its manifest and its directory as untrusted."""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any

import pytest

from odfa11y.errors import OutputError
from odfa11y.evidence import (
    Redactor,
    check_bundle,
    write_bundle,
)
from odfa11y.families.text import ADAPTER

if TYPE_CHECKING:
    from pathlib import Path

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


def test_a_manifest_name_that_is_not_valid_text_is_reported_not_fatal(tmp_path: Path) -> None:
    directory = bundle(tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["files"]["bad\ud800.txt"] = "0" * 64
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    problems = check_bundle(directory)
    assert any("unsafe name" in problem for problem in problems)
