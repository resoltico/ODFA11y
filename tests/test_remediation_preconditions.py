# SPDX-License-Identifier: MPL-2.0
"""Remediation refuses documents it cannot edit safely and keeps what it does not touch."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.errors import RemediationError
from odfa11y.odf import OdfDocument, PackageStorage, Part, ensure_metadata_part, qn
from odfa11y.remediation import SetMetadata, remediate

from .documents import OASIS, Variant, make_flat, make_package

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report


def ids(report: Report) -> set[str]:
    return {finding.rule_id for finding in report.findings}


def test_remediation_refuses_an_unrecognised_document(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(media_type="application/epub+zip"))
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="not a recognised OpenDocument"):
        remediate(source, destination, [SetMetadata(title="x")])
    assert not destination.exists()


def test_explicit_metadata_creates_a_missing_optional_package_part(tmp_path: Path) -> None:
    source = tmp_path / "nometa.odt"
    with (
        zipfile.ZipFile(make_package(tmp_path, "text")) as full,
        zipfile.ZipFile(source, "w") as cut,
    ):
        for member in full.infolist():
            if member.filename != "meta.xml":
                cut.writestr(member, full.read(member.filename))
    destination = tmp_path / "out.odt"
    assert remediate(source, destination, [SetMetadata(title="x")]).changed
    assert audit_odf(destination).metadata["title"] == "x"
    with zipfile.ZipFile(destination) as created:
        manifest = created.read("META-INF/manifest.xml")
        assert manifest.count(b'manifest:full-path="meta.xml"') == 1
    assert not remediate(destination, tmp_path / "again.odt", [SetMetadata(title="x")]).changed


@pytest.mark.parametrize("duplicate", [False, True])
def test_metadata_creation_preflights_conflicting_manifest_declarations(
    tmp_path: Path, *, duplicate: bool
) -> None:
    source = make_package(tmp_path, "text")
    storage = PackageStorage(source)
    storage.members.pop("meta.xml")
    storage.save(source)
    document = OdfDocument.open(source)
    manifest = document.tree(Part.MANIFEST).getroot()
    count = 2 if duplicate else 1
    for _ in range(count):
        entry = etree.SubElement(manifest, qn("manifest", "file-entry"))
        entry.set(qn("manifest", "full-path"), "meta.xml")
        entry.set(qn("manifest", "media-type"), "text/xml" if duplicate else "text/plain")
    with pytest.raises(RemediationError, match="duplicate or has a conflicting"):
        ensure_metadata_part(document)
    assert not document.has(Part.META)
    assert document.edit_count == 0


def test_invalid_metadata_language_prevents_earlier_valid_field_edits(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    original = etree.tostring(document.tree(Part.META))
    result = SetMetadata(title="A chosen title", language="not a language").apply(document)
    assert [outcome.status.value for outcome in result] == ["failed"]
    assert document.edit_count == 0
    assert etree.tostring(document.tree(Part.META)) == original


def test_editing_a_flat_document_keeps_comments_and_processing_instructions(
    tmp_path: Path,
) -> None:
    source = make_flat(tmp_path, "text")
    text = source.read_text(encoding="utf-8")
    declaration, rest = text.split("\n", 1)
    source.write_text(
        f"  {declaration}\n"
        '<?xml-stylesheet href="s.css" type="text/css"?>\n'
        f"<!-- keep me -->\n{rest}\n<!-- and me -->\n",
        encoding="utf-8",
    )
    destination = tmp_path / "out.fodt"
    remediate(source, destination, [SetMetadata(title="Changed")])
    saved = destination.read_text(encoding="utf-8")
    assert '<?xml-stylesheet href="s.css" type="text/css"?>' in saved
    assert "<!-- keep me -->" in saved
    assert "<!-- and me -->" in saved
    assert "Changed" in saved


def test_a_flat_document_without_metadata_gets_it_in_schema_order(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    text = source.read_text(encoding="utf-8")
    start, end = text.index("<office:meta>"), text.index("</office:meta>") + len("</office:meta>")
    source.write_text(text[:start] + text[end:], encoding="utf-8")
    destination = tmp_path / "out.fodt"
    remediate(source, destination, [SetMetadata(title="Added")])
    assert audit_odf(destination).metadata["title"] == "Added"
    assert "ODF900" not in ids(audit_odf(destination, schema=True))


def test_a_blank_title_is_refused_rather_than_written_empty(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text")
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="must not be blank"):
        remediate(source, destination, [SetMetadata(title="   ")])
    assert not destination.exists()


@pytest.mark.parametrize(("given", "written"), [("en_US", "en-US"), ("x-klingon", "x-klingon")])
def test_language_tags_are_normalised_or_private_use_and_stay_schema_valid(
    tmp_path: Path, given: str, written: str
) -> None:
    source = make_package(tmp_path, "text")
    destination = tmp_path / "out.odt"
    remediate(source, destination, [SetMetadata(language=given)])
    assert audit_odf(destination).metadata["language"] == written


def test_remediation_refuses_a_document_whose_parts_contradict_each_other(tmp_path: Path) -> None:
    for name, variant in {
        "manifest": Variant(manifest_media_type=OASIS + "spreadsheet"),
        "body": Variant(
            body="<office:spreadsheet><table:table table:name='A'/></office:spreadsheet>"
        ),
    }.items():
        source = make_package(tmp_path, "text", variant)
        with pytest.raises(RemediationError, match="nothing was written"):
            remediate(source, tmp_path / f"{name}.odt", [SetMetadata(title="x")])
        assert not (tmp_path / f"{name}.odt").exists()
