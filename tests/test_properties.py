# SPDX-License-Identifier: MPL-2.0
"""State invariants that must hold for every input, not just hand-picked examples."""

from __future__ import annotations

import contextlib
import tempfile
import zipfile
from pathlib import Path

from hypothesis import example, given
from hypothesis import strategies as st
from lxml import etree

from odfa11y.odf import (
    ODT_MIMETYPE,
    URI_RE,
    OdtPackage,
    qn,
    split_trailing_punctuation,
    text_is_preserved,
)
from odfa11y.remediation import linkify_plain_addresses, load_remediation_config
from odfa11y.report import AuditReport, Severity

from .fixtures import make_minimal_odt

PROSE = st.text(alphabet="abc XYZ.,;:()[]{}/@-_&", max_size=12)
ADDRESSES = st.sampled_from([
    "https://example.test/a_(b)",
    "http://example.test/path?q=1",
    "qa@example.test",
    "first.last+tag@sub.example.test",
])
FRAGMENTS = st.lists(st.one_of(PROSE, ADDRESSES), max_size=8)
MEMBER_NAMES = st.text(alphabet="abcdef/._-", min_size=1, max_size=12).filter(
    lambda name: name != "mimetype" and not name.endswith("/") and name not in {".", ".."}
)
MEMBERS = st.dictionaries(MEMBER_NAMES, st.binary(max_size=64), max_size=6)


def _paragraph_tree(text: str) -> etree._ElementTree:
    root = etree.Element(qn("office", "text"))
    etree.SubElement(root, qn("text", "p")).text = text
    return etree.ElementTree(root)


@given(st.text(alphabet="abc.,;:()[]{}/", max_size=16))
def test_trailing_punctuation_split_is_lossless_and_stable(raw: str) -> None:
    token, suffix = split_trailing_punctuation(raw)
    assert token + suffix == raw
    assert set(suffix) <= set(".,;:)]}")
    assert not token.endswith(tuple(".,;:"))
    assert split_trailing_punctuation(token) == (token, "")


@given(FRAGMENTS)
def test_linkification_preserves_visible_text_and_is_idempotent(fragments: list[str]) -> None:
    text = "".join(fragments)
    tree = _paragraph_tree(text)
    inserted = linkify_plain_addresses(tree)
    assert "".join(tree.getroot().itertext()) == text
    links = tree.getroot().findall(f".//{qn('text', 'a')}")
    assert len(links) == inserted
    for link in links:
        assert link.text is not None
        assert URI_RE.fullmatch(link.text)
    assert linkify_plain_addresses(tree) == 0


@given(st.lists(st.text(alphabet="ab ", max_size=4), max_size=8), st.data())
def test_text_preservation_accepts_exactly_the_removed_empty_blocks(
    after: list[str], data: st.DataObject
) -> None:
    blocks = list(after)
    removed = data.draw(st.integers(min_value=0, max_value=4))
    for _ in range(removed):
        blocks.insert(data.draw(st.integers(min_value=0, max_value=len(blocks))), "")
    assert text_is_preserved(tuple(blocks), tuple(after), removed_empty_blocks=removed)
    assert not text_is_preserved(tuple(blocks), tuple(after), removed_empty_blocks=removed + 1)


@given(MEMBERS)
def test_saved_package_round_trips_members_and_keeps_mimetype_first(
    members: dict[str, bytes],
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        package = OdtPackage(make_minimal_odt(root / "source.odt"))
        for name, data in members.items():
            package.write_member(name, data)
        saved = package.save(root / "saved.odt")
        reloaded = OdtPackage(saved)
        assert {name: reloaded.read(name) for name in members} == members
        with zipfile.ZipFile(saved) as archive:
            first = archive.infolist()[0]
            assert (first.filename, first.compress_type) == ("mimetype", zipfile.ZIP_STORED)
            assert archive.read("mimetype").decode("ascii") == ODT_MIMETYPE


@given(st.binary(max_size=256))
def test_arbitrary_bytes_are_loaded_or_rejected_with_value_error(payload: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "input.odt"
        path.write_bytes(payload)
        with contextlib.suppress(ValueError):
            OdtPackage(path)


@given(st.integers(min_value=0, max_value=4000), st.integers(min_value=0, max_value=255))
@example(offset=118, value=0)  # invalid deflate block length once escaped as zlib.error
@example(offset=1656, value=6)  # bogus member location once escaped as OSError on Windows
def test_corrupted_package_bytes_are_loaded_or_rejected_with_value_error(
    offset: int, value: int
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = make_minimal_odt(Path(directory) / "source.odt")
        data = bytearray(source.read_bytes())
        data[offset % len(data)] = value
        source.write_bytes(bytes(data))
        with contextlib.suppress(ValueError):
            OdtPackage(source)


@given(st.binary(max_size=128))
def test_arbitrary_configuration_bytes_are_accepted_or_rejected_with_value_error(
    payload: bytes,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "config.toml"
        path.write_bytes(payload)
        with contextlib.suppress(ValueError):
            load_remediation_config(path)


@given(st.lists(st.tuples(st.text(max_size=6), st.sampled_from(list(Severity))), max_size=10))
def test_report_counts_partition_findings(findings: list[tuple[str, Severity]]) -> None:
    report = AuditReport(subject="synthetic")
    for message, severity in findings:
        report.add("TST001", severity, message)
    assert report.error_count + report.warning_count + report.info_count == len(findings)
    assert report.passed is (report.error_count == 0)
    assert report.as_dict()["summary"]["errors"] == report.error_count
