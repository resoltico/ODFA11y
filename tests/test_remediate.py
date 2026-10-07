# SPDX-License-Identifier: MPL-2.0
"""The executor: fail-closed publication, postconditions and byte preservation."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

import pytest
from lxml import etree

from odfa11y.errors import OutputError, RemediationError
from odfa11y.odf import OdtDocument, OdtPackage, qn, select_elements
from odfa11y.remediation import (
    AltText,
    LinkifyAddresses,
    MarkHeaderRows,
    Operation,
    Outcome,
    SetAltText,
    SetMetadata,
    SetOdfVersion,
    Status,
    remediate,
)

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class Misbehaving(Operation):
    """A test operation whose edits are chosen by the test."""

    action: str
    name: ClassVar[str] = "misbehaving"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        content = document.edit("content.xml")
        paragraph = select_elements(content, "//text:p")[0]
        if self.action == "change-text":
            paragraph.text = "Different words"
        elif self.action == "break-schema":
            etree.SubElement(paragraph, qn("table", "table"))
        return (Outcome(self.name, Status.APPLIED, "did something", count=1),)


@dataclass(frozen=True, slots=True)
class Lying(Operation):
    """Claims a change without editing anything."""

    name: ClassVar[str] = "lying"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        return (Outcome(self.name, Status.APPLIED, "claims a change"),)


def test_full_remediation_publishes_a_valid_document_and_reports_each_outcome(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(
        tmp_path / "source.odt",
        with_plain_email=True,
        with_data_table=True,
        with_image_without_alt=True,
    )
    operations = [
        SetMetadata(title="New title", language="en-GB"),
        SetAltText({"Logo": AltText("Example logo", "Sample")}),
        MarkHeaderRows({"Data": 1}),
        LinkifyAddresses(),
    ]
    destination = tmp_path / "out.odt"
    result = remediate(source, destination, operations)
    assert result.destination == destination
    assert result.changed
    assert result.schema_check.startswith("no new violations against ODF 1.4")
    assert {o.status for o in result.outcomes} == {Status.APPLIED, Status.UNCHANGED}
    again = remediate(destination, tmp_path / "again.odt", operations)
    assert not again.changed
    for member in ("content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml"):
        assert OdtPackage(destination).read(member) == OdtPackage(tmp_path / "again.odt").read(
            member
        )


def test_failed_outcomes_abort_the_run_listing_every_failure_and_write_nothing(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    destination.write_bytes(b"existing")
    operations = [SetAltText({"A": AltText("x"), "B": AltText("y")}), MarkHeaderRows({"C": 1})]
    with pytest.raises(RemediationError) as raised:
        remediate(source, destination, operations)
    for key in ("[A]", "[B]", "[C]"):
        assert key in str(raised.value)
    assert destination.read_bytes() == b"existing"


def test_dry_run_reports_outcomes_and_writes_nothing(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    result = remediate(source, destination, [SetMetadata(title="Dry")], dry_run=True)
    assert result.dry_run
    assert result.destination is None
    assert result.changed
    assert not destination.exists()


def test_destination_must_differ_from_the_source(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    link = tmp_path / "alias.odt"
    link.symlink_to(source)
    for destination in (source, tmp_path / "." / "source.odt", link):
        with pytest.raises(OutputError):
            remediate(source, destination, [])


def test_text_changes_are_rejected_before_publication(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="text changed"):
        remediate(source, destination, [Misbehaving("change-text")])
    assert not destination.exists()


def test_new_schema_violations_are_rejected_before_publication(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="schema violations"):
        remediate(source, destination, [Misbehaving("break-schema")])
    assert not destination.exists()


def test_pre_existing_schema_violations_do_not_block_remediation(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_data_table=True)
    package = OdtPackage(source)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    broken = tmp_path / "broken.odt"
    package.save(broken)
    result = remediate(broken, tmp_path / "out.odt", [SetMetadata(title="Still fine")])
    assert "pre-existing" in result.schema_check
    assert "(0 pre-existing)" not in result.schema_check


def test_an_operation_that_misreports_its_edits_is_an_internal_error(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    with pytest.raises(RemediationError, match="Internal error"):
        remediate(source, tmp_path / "out.odt", [Lying()])


def test_unmentioned_members_and_foreign_markup_survive_byte_for_byte(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_image_without_alt=True)
    package = OdtPackage(source)
    content = package.read("content.xml").replace(
        b"<office:text>",
        b'<office:text><!-- keep me --><?keep this?><x:ext xmlns:x="urn:example" x:a="1"/>',
    )
    package.write_member("content.xml", content)
    package.write_member("Extra/blob.bin", b"\x00\x01opaque")
    marked = tmp_path / "marked.odt"
    package.save(marked)

    destination = tmp_path / "out.odt"
    remediate(marked, destination, [SetMetadata(title="Only metadata changes")])
    before, after = OdtPackage(marked), OdtPackage(destination)
    for member in (
        "content.xml",
        "styles.xml",
        "META-INF/manifest.xml",
        "Extra/blob.bin",
        "Pictures/logo.svg",
    ):
        assert after.read(member) == before.read(member)
    assert after.read("meta.xml") != before.read("meta.xml")

    remediate(
        marked, tmp_path / "out2.odt", [LinkifyAddresses(), SetAltText({"Logo": AltText("T")})]
    )
    content_after = OdtPackage(tmp_path / "out2.odt").read("content.xml")
    assert b"keep me" in content_after
    assert b"<?keep this?>" in content_after
    assert b'x:a="1"' in content_after
    assert OdtPackage(tmp_path / "out2.odt").read("styles.xml") == before.read("styles.xml")


def test_saved_archive_keeps_the_mimetype_invariant(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    remediate(source, destination, [SetOdfVersion("1.3")])
    with zipfile.ZipFile(destination) as archive:
        first = archive.infolist()[0]
        assert (first.filename, first.compress_type) == ("mimetype", zipfile.ZIP_STORED)
    assert OdtDocument.open(destination).text_snapshot()
