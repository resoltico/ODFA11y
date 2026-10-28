# SPDX-License-Identifier: MPL-2.0
"""Live XML changes, cache generations and access policy do not rely on edit declarations."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from lxml import etree

from odfa11y.adapter import Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.errors import PackageError, RemediationError
from odfa11y.odf import KINDS, NS, OdfDocument, PackageStorage, Part, Use, qn
from odfa11y.odf.protection import PackageProtection
from odfa11y.remediation import SetMetadata, remediate

from .fixtures import make_minimal_odt

CORPUS = Path(__file__).parent
CORPUS_DOCUMENTS = tuple(
    directory / entry["file"]
    for directory, section in [
        (CORPUS / "corpus", "document"),
        (CORPUS / "family_corpus", "documents"),
    ]
    for entry in tomllib.loads((directory / "manifest.toml").read_text())[section]
)

CORPUS_DOCUMENTS += tuple(
    source
    for directory in [CORPUS / "corpus/sources", CORPUS / "family_corpus/sources"]
    for source in sorted(directory.rglob("*"))
    if source.suffix.startswith(".fod")
    or source.suffix in {kind.extension for kind in KINDS.values()}
)


def _tree_metadata_edit(
    operation: SetMetadata, document: OdfDocument, status: Status
) -> tuple[Outcome, ...]:
    meta = document.tree(Part.META).find("office:meta", NS)
    assert meta is not None
    title = meta.find(qn("dc", "title"))
    if title is None:
        title = etree.SubElement(meta, qn("dc", "title"))
    title.text = operation.title
    return (Outcome(operation.name, status, "Title"),)


def test_undeclared_tree_mutation_is_published_and_other_members_keep_their_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SetMetadata,
        "apply",
        lambda operation, document: _tree_metadata_edit(operation, document, Status.APPLIED),
    )
    source = make_minimal_odt(tmp_path / "source.odt")
    original = source.read_bytes()
    destination = tmp_path / "result.odt"
    result = remediate(source, destination, [SetMetadata(title="Reviewed title")])
    assert result.changed
    before, after = PackageStorage(source), PackageStorage(destination)
    for member in before.member_names():
        if member != "meta.xml":
            assert after.read(member) == before.read(member), member
    assert (
        OdfDocument
        .open(destination)
        .tree(Part.META)
        .findtext("office:meta/dc:title", namespaces=NS)
        == "Reviewed title"
    )
    assert source.read_bytes() == original


def test_mutation_misreported_as_unchanged_refuses_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SetMetadata,
        "apply",
        lambda operation, document: _tree_metadata_edit(operation, document, Status.UNCHANGED),
    )
    source = make_minimal_odt(tmp_path / "source.odt")
    destination = tmp_path / "result.odt"
    with pytest.raises(RemediationError, match="reported no change but changed"):
        remediate(source, destination, [SetMetadata(title="Reviewed title")])
    assert not destination.exists()


def test_lazy_parsing_and_noop_reads_do_not_dirty_or_rewrite_members(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    document = OdfDocument.open(source)
    before = document.checkpoint()
    for part in Part:
        if document.has(part):
            document.tree(part)
    assert not document.changed_since(before)
    assert not document.dirty
    output = document.save(tmp_path / "copy.odt")
    original, actual = PackageStorage(source), PackageStorage(output)
    assert {name: actual.read(name) for name in actual.member_names()} == {
        name: original.read(name) for name in original.member_names()
    }


def test_generation_boundaries_drop_derived_state_but_an_operation_can_update_its_catalog(
    tmp_path: Path,
) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    tree = document.tree(Part.CONTENT)

    def count() -> dict[str, int]:
        return {"paragraphs": len(tree.findall(".//text:p", NS))}

    catalog = document.derived("paragraphs", count)
    checkpoint = document.checkpoint()
    body = tree.find("office:body/office:text", NS)
    assert body is not None
    etree.SubElement(body, qn("text", "p")).text = "Added paragraph"
    catalog["paragraphs"] += 1
    assert document.derived("paragraphs", count) is catalog
    assert document.changed_since(checkpoint) == frozenset({"content.xml"})
    updated = document.derived("paragraphs", count)
    assert updated is not catalog
    assert updated == catalog


def test_namespace_binding_changes_ignored_by_c14n_are_detected(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    tree = document.tree(Part.CONTENT)
    left = etree.fromstring(b'<root xmlns:of="urn:formula:a" formula="of:=1"/>')
    right = etree.fromstring(b'<root xmlns:of="urn:formula:b" formula="of:=1"/>')
    tree._setroot(left)  # noqa: SLF001  lxml documents this tree-root replacement API.
    checkpoint = document.checkpoint()
    tree._setroot(right)  # noqa: SLF001  lxml documents this tree-root replacement API.
    assert etree.tostring(left, method="c14n2") == etree.tostring(right, method="c14n2")
    assert document.changed_since(checkpoint) == frozenset({"content.xml"})


@pytest.mark.parametrize(
    "source", CORPUS_DOCUMENTS, ids=lambda path: path.relative_to(CORPUS).as_posix()
)
def test_every_corpus_audit_leaves_live_trees_and_source_bytes_unchanged(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = source.read_bytes()
    document = OdfDocument.open(source)
    before = document.checkpoint()
    monkeypatch.setattr(OdfDocument, "open", lambda _source: document)
    audit_odf(source, schema=True)
    assert not document.changed_since(before)
    assert source.read_bytes() == original


@pytest.mark.parametrize("use", list(Use))
@pytest.mark.parametrize(
    "protection",
    [
        PackageProtection(encrypted=True),
        PackageProtection(malformed_manifest="Malformed"),
        PackageProtection(ambiguous_members=("content.xml",)),
        PackageProtection(unsafe_members=("../unsafe",)),
        PackageProtection(signatures=("META-INF/documentsignatures.xml",)),
    ],
)
def test_one_access_gate_enforces_protection_for_every_use(
    tmp_path: Path, use: Use, protection: PackageProtection
) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    document.protection = protection
    if protection.inspection_blocked or use == Use.REMEDIATE:
        with pytest.raises(PackageError, match="cannot establish"):
            document.require(use)
    else:
        document.require(use)


def test_replacing_stored_xml_cannot_bypass_cached_tree_validation(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    document.tree(Part.CONTENT)
    document.storage.write_member("content.xml", b"<different/>")
    with pytest.raises(PackageError, match="behind a cached tree"):
        document.save(tmp_path / "out.odt")
    assert not (tmp_path / "out.odt").exists()


def test_a_saved_tree_remains_coherent_for_further_changes_and_saves(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    title = document.tree(Part.META).find("office:meta/dc:title", NS)
    assert title is not None
    title.text = "First title"
    document.save(tmp_path / "first.odt")
    checkpoint = document.checkpoint()
    title.text = "Second title"
    assert document.changed_since(checkpoint) == frozenset({"meta.xml"})
    output = document.save(tmp_path / "second.odt")
    assert (
        OdfDocument.open(output).tree(Part.META).findtext("office:meta/dc:title", namespaces=NS)
        == "Second title"
    )
