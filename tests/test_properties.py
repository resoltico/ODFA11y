# SPDX-License-Identifier: MPL-2.0
"""State invariants that must hold for every input, not just hand-picked examples."""

from __future__ import annotations

import contextlib
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from hypothesis import example, given
from hypothesis import strategies as st
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.config import load_config
from odfa11y.errors import ConfigError, PackageError
from odfa11y.families.text import (
    URI_RE,
    AltText,
    HeaderRows,
    LinkifyAddresses,
    MarkHeaderRows,
    RemoveEmptySpacers,
    SetAltText,
    linkify_plain_addresses,
    split_trailing_punctuation,
    text_is_preserved,
)
from odfa11y.odf import OdfDocument, PackageStorage, is_unsafe_member_name, qn, validate
from odfa11y.remediation import SetMetadata, remediate
from odfa11y.report import RULES, Report

from .fixtures import TEXT_MEDIA_TYPE, make_minimal_odt

if TYPE_CHECKING:
    from .fixtures import Features

PROSE = st.text(alphabet="abc XYZ.,;:()[]{}/@-_&", max_size=12)
ADDRESSES = st.sampled_from([
    "https://example.test/a_(b)",
    "http://example.test/path?q=1",
    "qa@example.test",
    "first.last+tag@sub.example.test",
])
FRAGMENTS = st.lists(st.one_of(PROSE, ADDRESSES), max_size=8)
MEMBER_NAMES = st.text(alphabet="abcdef/._-", min_size=1, max_size=12).filter(
    lambda name: name != "mimetype" and not name.endswith("/") and not is_unsafe_member_name(name)
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
        package = PackageStorage(make_minimal_odt(root / "source.odt"))
        for name, data in members.items():
            package.write_member(name, data)
        saved = package.save(root / "saved.odt")
        reloaded = PackageStorage(saved)
        assert {name: reloaded.read(name) for name in members} == members
        with zipfile.ZipFile(saved) as archive:
            first = archive.infolist()[0]
            assert (first.filename, first.compress_type) == ("mimetype", zipfile.ZIP_STORED)
            assert archive.read("mimetype").decode("ascii") == TEXT_MEDIA_TYPE


@given(st.binary(max_size=256))
def test_arbitrary_bytes_are_loaded_or_rejected_with_a_package_error(payload: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "input.odt"
        path.write_bytes(payload)
        with contextlib.suppress(PackageError):
            PackageStorage(path)


@given(st.integers(min_value=0, max_value=4000), st.integers(min_value=0, max_value=255))
@example(offset=118, value=0)  # invalid deflate block length once escaped as zlib.error
@example(offset=1656, value=6)  # bogus member location once escaped as OSError on Windows
def test_corrupted_package_bytes_are_loaded_or_rejected_with_a_package_error(
    offset: int, value: int
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = make_minimal_odt(Path(directory) / "source.odt")
        data = bytearray(source.read_bytes())
        data[offset % len(data)] = value
        source.write_bytes(bytes(data))
        with contextlib.suppress(PackageError):
            PackageStorage(source)


@given(st.binary(max_size=128))
def test_arbitrary_configuration_bytes_are_accepted_or_rejected_with_a_config_error(
    payload: bytes,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "config.toml"
        path.write_bytes(payload)
        with contextlib.suppress(ConfigError):
            load_config(path)


@given(st.lists(st.sampled_from(sorted(RULES)), max_size=10))
def test_report_counts_partition_findings(rule_ids: list[str]) -> None:
    report = Report(kind="odt", subject="synthetic")
    for rule_id in rule_ids:
        report.add(RULES[rule_id])
    assert report.error_count + report.warning_count + report.info_count == len(rule_ids)
    assert report.passed is (report.error_count == 0)
    assert report.as_dict()["summary"]["errors"] == report.error_count


FEATURE_FLAGS = st.fixed_dictionaries({
    "with_plain_email": st.booleans(),
    "with_data_table": st.booleans(),
    "with_image_without_alt": st.booleans(),
    "add_blank_body_paragraph": st.booleans(),
})
CHOICES = st.fixed_dictionaries({
    "title": st.booleans(),
    "language": st.booleans(),
    "alt": st.booleans(),
    "headers": st.booleans(),
    "linkify": st.booleans(),
    "spacers": st.booleans(),
})


@given(FEATURE_FLAGS, CHOICES)
def test_any_applicable_operation_subset_keeps_the_schema_valid_and_is_idempotent(
    features: Features, choices: dict[str, bool]
) -> None:
    operations = []
    if choices["title"]:
        operations.append(SetMetadata(title="Generated title"))
    if choices["language"]:
        operations.append(SetMetadata(language="de-AT"))
    if choices["alt"] and features.get("with_image_without_alt"):
        operations.append(SetAltText({"Logo": AltText("Logo", "Description")}))
    if choices["headers"] and features.get("with_data_table"):
        operations.append(MarkHeaderRows({"Data": HeaderRows(1)}))
    if choices["linkify"]:
        operations.append(LinkifyAddresses())
    if choices["spacers"]:
        operations.append(RemoveEmptySpacers())
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = make_minimal_odt(root / "source.odt", **features)
        first = remediate(source, root / "first.odt", operations)
        assert validate(OdfDocument.open(root / "first.odt")).violations == {}
        second = remediate(root / "first.odt", root / "second.odt", operations)
        assert all(outcome.status is not Status.APPLIED for outcome in second.outcomes)
        for member in ("content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml"):
            assert PackageStorage(root / "first.odt").read(member) == PackageStorage(
                root / "second.odt"
            ).read(member)
        assert first.destination == root / "first.odt"
