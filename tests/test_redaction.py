# SPDX-License-Identifier: MPL-2.0
"""Redaction keeps local paths out of everything a bundle publishes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from odfa11y.evidence import (
    Redactor,
    check_bundle,
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


def test_known_locations_are_replaced_only_as_whole_path_prefixes(tmp_path: Path) -> None:
    redactor = Redactor.for_locations({"run": tmp_path / "run1"})
    cleaned = redactor.record({
        "ok": f"{tmp_path}/run1/x.pdf",
        "sibling": f"{tmp_path}/run10/x.pdf",
        "word": "layout without outputs and overflows",
    })
    assert cleaned["ok"] == "<run>/x.pdf"
    assert "<run>" not in cleaned["sibling"]
    assert cleaned["sibling"].endswith("<path>/x.pdf") or "run10" not in cleaned["sibling"]
    assert cleaned["word"] == "layout without outputs and overflows"


def test_a_relative_location_never_replaces_text_inside_words() -> None:
    redactor = Redactor.for_locations({"output": Path("out"), "source": Path("..")})
    text = "layout without outputs.. wait; text.remediation; reflects"
    assert redactor.text(text) == text


@pytest.mark.parametrize(
    ("leaky", "kept"),
    [
        ("/home/John Smith/My Docs/f.odt", "f.odt"),
        ("C:\\Users\\John Smith\\f.odt", "f.odt"),
        ("/home/me/a(1)/b/f.odt", "f.odt"),
        ("../../secret/f.odt", "f.odt"),
        ("~/docs/f.odt", "f.odt"),
        ("file://host/share/f.odt", "f.odt"),
        ("\\\\server\\share\\f.odt", "f.odt"),
    ],
)
def test_other_absolute_paths_keep_only_the_file_name(leaky: str, kept: str) -> None:
    cleaned = Redactor(()).record({"message": f"failed on {leaky} just now"})["message"]
    assert kept in cleaned
    for secret in ("John", "Smith", "secret", "docs", "server", "share", "host", "a(1)"):
        assert secret not in cleaned, (leaky, cleaned)


def test_dictionary_keys_are_redacted_too() -> None:
    cleaned = Redactor(()).record({"/home/someone/x/key.odt": 1})
    assert list(cleaned) == ["<path>/key.odt"]


def test_text_artifacts_are_redacted_and_binary_ones_are_not(tmp_path: Path) -> None:
    work = tmp_path / "scratch"
    work.mkdir()
    xml = tmp_path / "report.xml"
    xml.write_text(f"<name>{work}/remediated.pdf</name>", encoding="utf-8")
    binary = tmp_path / "data.bin"
    binary.write_bytes(str(work).encode())
    redactor = Redactor.for_locations({"work": work})
    target = tmp_path / "bundle"
    write_bundle(
        target,
        record(),
        {"report.xml": xml, "data.bin": binary},
        redactor,
        diagnostics={"report.xml"},
    )
    assert etree.parse(target / "report.xml").getroot().text == "<work>/remediated.pdf"
    assert (target / "data.bin").read_bytes() == str(work).encode()
    assert check_bundle(target) == []


def test_a_location_matches_whatever_separators_the_text_uses(tmp_path: Path) -> None:
    redactor = Redactor.for_locations({"run": tmp_path / "run1"})
    posix = (tmp_path / "run1").as_posix()
    backslashed = posix.replace("/", "\\")
    for spelling in (posix, backslashed):
        assert redactor.record({"k": f"{spelling}/x.pdf"})["k"] == "<run>/x.pdf"
