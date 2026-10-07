# SPDX-License-Identifier: MPL-2.0
"""Graphic review binds real resources while repeated audit work stays bounded."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import (
    GraphicDescription,
    GraphicIdentity,
    graphic_identity,
    graphics_fingerprint,
    local_resource_path,
)
from odfa11y.families.text import SetGraphicDescriptions
from odfa11y.families.text.semantics import audit_images
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.report import Report

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def _graphic(tmp_path: Path) -> tuple[OdfDocument, etree._Element]:
    document = OdfDocument.open(
        make_minimal_odt(tmp_path / "source.odt", with_image_without_alt=True)
    )
    return document, select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("Pictures/file%20name.svg", "Pictures/file name.svg"),
        ("./Pictures/../Pictures/caf%C3%A9.svg#fragment", "Pictures/café.svg"),
        ("Pictures/a%3Fb%23c.svg", "Pictures/a?b#c.svg"),
        ("Object%201/", "Object 1"),
        (".", "."),
        ("#fragment", None),
        ("../secret", None),
        ("folder/../../secret", None),
        ("%2Fabsolute", None),
        ("%2e%2e/secret", None),
        ("%43%3Asecret", None),
        ("\\server\\secret", None),
        ("Pictures/a%5Cb.svg", None),
        ("file:///secret", None),
        ("https://example.test/image.svg", None),
        ("//example.test/image.svg", None),
        ("image.svg?revision=1", None),
        ("image.svg?", None),
        ("image.svg#%FF", None),
        ("image.svg#%2G", None),
        ("Pictures/%FF.svg", None),
        ("Pictures/%2G.svg", None),
        ("Pictures/%.svg", None),
        ("Pictures/%00.svg", None),
        ("Pictures/%7F.svg", None),
        ("Pictures/file name.svg", None),
        ("Pictures/file\tname.svg", None),
        ("Pictures/\ud800.svg", None),
    ],
)
def test_local_references_are_strict_and_confined(href: str, expected: str | None) -> None:
    assert local_resource_path(href) == expected


@pytest.mark.parametrize(
    ("href", "member", "kind"),
    [
        ("Pictures/file%20name.svg", "Pictures/file name.svg", "image"),
        ("Object%201", "Object 1/content.xml", "object"),
        ("Object%201/", "Object 1/Pictures/chart.svg", "object"),
        ("Object%201/", "Object 1/styles.xml", "object-ole"),
    ],
)
def test_payload_drift_is_detected_before_any_graphic_edit(
    tmp_path: Path, href: str, member: str, kind: str
) -> None:
    document, frame = _graphic(tmp_path)
    payload = frame.find(qn("draw", "image"))
    assert payload is not None
    payload.tag = qn("draw", kind)
    payload.set(qn("xlink", "href"), href)
    document.storage.write_member(member, b"reviewed resource")
    reviewed = graphics_fingerprint(document, [frame])
    document.storage.write_member(member, b"changed resource")
    assert graphics_fingerprint(document, [frame]) != reviewed
    result = SetGraphicDescriptions({
        "Logo": GraphicDescription("Title", fingerprint=reviewed)
    }).apply(document)
    assert result[0].status is Status.FAILED
    assert document.edit_count == 0
    assert frame.find(qn("svg", "title")) is None


def test_directory_identity_includes_names_and_is_confined_to_the_exact_prefix(
    tmp_path: Path,
) -> None:
    document, frame = _graphic(tmp_path)
    payload = frame.find(qn("draw", "image"))
    assert payload is not None
    payload.tag = qn("draw", "object")
    payload.set(qn("xlink", "href"), "Object1")
    document.storage.write_member("Object1/content.xml", b"chart content")
    before = graphics_fingerprint(document, [frame])
    document.storage.write_member("Object10/content.xml", b"unrelated object")
    assert graphics_fingerprint(document, [frame]) == before
    document.storage.write_member("Object1/styles.xml", b"chart content")
    assert graphics_fingerprint(document, [frame]) != before


@pytest.mark.parametrize("duplicate_names", [True, False])
def test_an_audit_hashes_each_frame_and_shared_payload_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, duplicate_names: bool
) -> None:
    document, frame = _graphic(tmp_path)
    count = 64
    parent = frame.getparent()
    assert parent is not None
    for index in range(1, count):
        clone = deepcopy(frame)
        if not duplicate_names:
            clone.set(qn("draw", "name"), f"Graphic {index}")
        parent.append(clone)
    hash_calls = []
    read_calls = []
    group_hashes = []
    protected = graphic_identity.protected_xml
    read = document.storage.read
    dump = graphic_identity.json.dumps

    def observe_hash(node: etree._Element, *, omitted_elements: tuple[str, ...]) -> str:
        hash_calls.append(node)
        return protected(node, omitted_elements=omitted_elements)

    def observe_dump(value: object, *, sort_keys: bool) -> str:
        if isinstance(value, list) and value and isinstance(value[0], list):
            group_hashes.append(value)
        return dump(value, sort_keys=sort_keys)

    def observe_read(name: str) -> bytes:
        read_calls.append(name)
        return read(name)

    monkeypatch.setattr(graphic_identity, "protected_xml", observe_hash)
    monkeypatch.setattr(document.storage, "read", observe_read)
    monkeypatch.setattr(graphic_identity.json, "dumps", observe_dump)
    report = Report(kind="odt", subject="synthetic")
    audit_images(document, report)
    assert len(report.findings) == count
    assert len(hash_calls) == count
    assert read_calls == ["Pictures/logo.svg"]
    assert len(group_hashes) == (1 if duplicate_names else count)
    if duplicate_names:
        assert len({finding.details["fingerprint"] for finding in report.findings}) == 1


def test_indexed_groups_are_immutable_and_fresh_contexts_observe_mutations(tmp_path: Path) -> None:
    document, frame = _graphic(tmp_path)
    context = GraphicIdentity(document, [frame])
    group = context.matching("Logo")
    assert isinstance(group, tuple)
    assert context.matching("Logo") is group
    before = context.fingerprint(group)
    frame.set(qn("svg", "width"), "2cm")
    assert graphics_fingerprint(document, [frame]) != before
    assert context.matching("missing") == ()


def test_logical_row_positions_are_indexed_once_and_ignore_header_wrappers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = OdfDocument.open(
        make_minimal_odt(tmp_path / "rows.odt", with_data_table=True, with_image_without_alt=True)
    )
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    rows = select_elements(table, "./table:table-row")
    rows[0].set(qn("table", "number-rows-repeated"), "4")
    paragraph = select_elements(rows[1], ".//text:p")[0]
    paragraph.append(frame)
    reviewed = graphics_fingerprint(document, [frame])
    wrapper = deepcopy(rows[0])
    wrapper.set(qn("table", "number-rows-repeated"), "1")
    rows[0].set(qn("table", "number-rows-repeated"), "3")
    table.insert(table.index(rows[0]), wrapper)
    assert graphics_fingerprint(document, [frame]) == reviewed
    headers = etree.Element(qn("table", "table-header-rows"))
    table.insert(table.index(wrapper), headers)
    for row in (wrapper, rows[0], rows[1]):
        headers.append(row)
    assert graphics_fingerprint(document, [frame]) == reviewed
    frames = [frame]
    for _ in range(63):
        clone = deepcopy(frame)
        paragraph.append(clone)
        frames.append(clone)
    calls = []
    declarations = graphic_identity.declarations

    def observe(table_node: etree._Element, axis: str) -> list[etree._Element]:
        calls.append(axis)
        return declarations(table_node, axis)

    monkeypatch.setattr(graphic_identity, "declarations", observe)
    identity = GraphicIdentity(document, frames)
    identity.fingerprint(identity.matching("Logo"))
    assert calls == ["rows"]
    rows[0].set(qn("table", "number-rows-repeated"), "4")
    assert graphics_fingerprint(document, [frame]) != reviewed
