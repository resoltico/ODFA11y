# SPDX-License-Identifier: MPL-2.0
"""Finding locations are logical: the same document audits alike as a package or flat XML."""

from __future__ import annotations

import json
import zipfile
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.cli import main

from .documents import Variant, make_flat, make_package

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

BODY = (
    "<office:text>"
    '<text:h text:outline-level="2">1. Overview</text:h>'
    "<text:p>Visit https://example.org today.</text:p>"
    "<text:p>Plain prose.</text:p>"
    "<text:p>Write to someone@example.com.</text:p>"
    '<text:h text:outline-level="4">Details</text:h>'
    '<table:table table:name="Data">'
    "<table:table-column/><table:table-column/>"
    "<table:table-row><table:table-cell><text:p>Item</text:p></table:table-cell>"
    "<table:table-cell><text:p>Amount</text:p></table:table-cell></table:table-row>"
    "<table:table-row><table:table-cell><text:p>A</text:p></table:table-cell>"
    "<table:table-cell><text:p>10</text:p></table:table-cell></table:table-row>"
    "</table:table>"
    "<table:table>"
    "<table:table-column/><table:table-column/>"
    "<table:table-row><table:table-cell><text:p>Key</text:p></table:table-cell>"
    "<table:table-cell><text:p>Value</text:p></table:table-cell></table:table-row>"
    "<table:table-row><table:table-cell><text:p>B</text:p></table:table-cell>"
    "<table:table-cell><text:p>20</text:p></table:table-cell></table:table-row>"
    "</table:table>"
    '<text:p><draw:frame draw:name="Logo"><draw:image xlink:href="Pictures/logo.svg"/>'
    "</draw:frame></text:p>"
    "</office:text>"
)

EXPECTED = {
    ("TXT002", "content/heading[1]"),
    ("TXT002", "content/heading[2]"),
    ("TXT003", "content/heading[1]"),
    ("TXT010", "content/frame[name=Logo]"),
    ("TXT021", "content/table[name=Data]"),
    ("TXT021", "content/table[2]"),
    ("TXT030", "content/paragraph[1]"),
    ("TXT030", "content/paragraph[3]"),
}


def _logical(source: Path) -> set[tuple[str, str]]:
    report = audit_odf(source)
    for finding in report.findings:
        assert finding.location is None or finding.location.member is None, finding
    return {(f.rule_id, f.location.path) for f in report.findings if f.location is not None}


def _without_metadata(source: Path, element: str) -> None:
    """Remove a metadata element from a package or a flat document."""
    if source.suffix.startswith(".fo"):
        text = source.read_text(encoding="utf-8")
        source.write_text(text.replace(element, ""), encoding="utf-8")
        return
    with zipfile.ZipFile(source) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    members["meta.xml"] = members["meta.xml"].replace(element.encode(), b"")
    with zipfile.ZipFile(source, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_STORED)


@pytest.mark.parametrize("make", [make_package, make_flat], ids=["package", "flat"])
def test_body_findings_are_located_by_logical_path(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    assert _logical(make(tmp_path, "text", Variant(body=BODY))) >= EXPECTED


def test_package_and_flat_documents_yield_identical_locations(tmp_path: Path) -> None:
    packaged = tmp_path / "package"
    flat = tmp_path / "flat"
    packaged.mkdir()
    flat.mkdir()
    variant = Variant(body=BODY)
    assert _logical(make_package(packaged, "text", variant)) == _logical(
        make_flat(flat, "text", variant)
    )


def test_metadata_findings_are_located_by_field_in_both_layouts(tmp_path: Path) -> None:
    for make in (make_package, make_flat):
        source = make(tmp_path, "text", Variant())
        _without_metadata(source, "<dc:title>Synthetic document</dc:title>")
        _without_metadata(source, "<dc:language>en-GB</dc:language>")
        assert _logical(source) >= {("META001", "meta/title"), ("META002", "meta/language")}


def test_a_physical_member_name_is_never_the_logical_path(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(body=BODY, manifest_media_type="text/plain"))
    report = audit_odf(source)
    members = {"content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml", "mimetype"}
    paths = {f.location.path for f in report.findings if f.location is not None}
    assert paths
    assert paths.isdisjoint(members)
    assert not any(path.endswith(".xml") for path in paths)


def test_package_level_findings_keep_the_member_beside_the_logical_path(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(manifest_media_type="text/plain"))
    finding = next(f for f in audit_odf(source).findings if f.rule_id == "ODF004")
    assert finding.location is not None
    assert (finding.location.path, finding.location.member) == ("manifest", "META-INF/manifest.xml")


def test_json_report_serializes_the_path_and_the_member(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_package(tmp_path, "text", Variant(body=BODY, manifest_media_type="text/plain"))
    main(["audit", str(source), "--format", "json"])
    report = json.loads(capsys.readouterr().out)
    locations = {f["rule_id"]: f["location"] for f in reversed(report["findings"])}
    assert report["format"] == 4
    assert locations["TXT030"] == {"path": "content/paragraph[1]", "member": None}
    assert locations["ODF004"] == {"path": "manifest", "member": "META-INF/manifest.xml"}
