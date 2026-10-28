# SPDX-License-Identifier: MPL-2.0
"""Protection declarations stop guarded work before content parsing or operation calls."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

import odfa11y.odf
from odfa11y.errors import PackageError
from odfa11y.odf import NS, OdfDocument, PackageStorage, qn
from odfa11y.pipeline.native import export_document
from odfa11y.remediation import SetMetadata
from odfa11y.source_audit import audit_odf, prepare_plan
from tests.fixtures.operations import execute_operations
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize(
    "name", ["documentsignatures.xml", "macrosignatures.xml", "custom-signatures.xml"]
)
@pytest.mark.parametrize("payload", [b"", b"not XML"])
def test_declared_signature_is_unverified_and_all_remediation_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, payload: bytes
) -> None:
    source = make_minimal_odt(tmp_path / "signed.odt")
    storage = PackageStorage(source)
    storage.write_member("META-INF/" + name, payload)
    storage.save(source)
    original = source.read_bytes()
    report = audit_odf(source, schema=True)
    assert "PKG008" in {finding.rule_id for finding in report.findings}
    assert "cryptography" in next(f.message for f in report.findings if f.rule_id == "PKG008")

    def forbidden(*_args: object) -> None:
        pytest.fail("operation executed for signed input")

    monkeypatch.setattr(SetMetadata, "apply", forbidden)
    destination = tmp_path / "output.odt"
    destination.write_bytes(b"existing")
    for operations in ([], [SetMetadata(title="Changed")], [SetMetadata()]):
        for dry_run in (False, True):
            with pytest.raises(PackageError, match="Protected"):
                execute_operations(source, destination, operations, dry_run=dry_run)
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"existing"


def _key_declaration(manifest: etree._Element) -> None:
    # Invented base64 key/cipher bytes: schema structure, not a cryptography claim.
    key = etree.SubElement(manifest, qn("manifest", "encrypted-key"))
    keyinfo = etree.SubElement(key, qn("manifest", "keyinfo"))
    data = etree.SubElement(keyinfo, qn("manifest", "PGPData"))
    etree.SubElement(data, qn("manifest", "PGPKeyID")).text = "AAAAAAAAAAA="
    cipher = etree.SubElement(key, qn("manifest", "CipherData"))
    etree.SubElement(cipher, qn("manifest", "CipherValue")).text = "AAAAAAAAAAAAAAAAAAAAAA=="


def encrypted_manifest(storage: PackageStorage, member: str, declaration: str) -> bytes:
    # Reuse original file entries once, retaining alias coverage without string-rewriting
    # namespace URIs or adding a second declaration for an existing content.xml entry.
    original = storage.parse_xml("META-INF/manifest.xml").getroot()
    manifest = etree.Element(qn("manifest", "manifest"), nsmap={"m": NS["manifest"]})
    manifest.attrib.update(original.attrib)
    if declaration == "encrypted-key":
        _key_declaration(manifest)
    manifest.extend(list(original))
    matches = [node for node in manifest if node.get(qn("manifest", "full-path")) == member]
    if matches:
        assert len(matches) == 1
        entry = matches[0]
    else:
        entry = etree.SubElement(manifest, qn("manifest", "file-entry"))
        entry.set(qn("manifest", "full-path"), member)
        entry.set(qn("manifest", "media-type"), "application/octet-stream")
    if declaration == "encryption-data":
        entry.set(qn("manifest", "size"), "24")
        encryption = etree.SubElement(entry, qn("manifest", "encryption-data"))
        encryption.set(qn("manifest", "checksum-type"), "SHA1/1K")
        encryption.set(qn("manifest", "checksum"), "AAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        algorithm = etree.SubElement(encryption, qn("manifest", "algorithm"))
        algorithm.set(qn("manifest", "algorithm-name"), "Blowfish CFB")
        algorithm.set(qn("manifest", "initialisation-vector"), "AAAAAAAAAAA=")
        start = etree.SubElement(encryption, qn("manifest", "start-key-generation"))
        start.set(qn("manifest", "start-key-generation-name"), "SHA1")
        start.set(qn("manifest", "key-size"), "20")
        derivation = etree.SubElement(encryption, qn("manifest", "key-derivation"))
        derivation.set(qn("manifest", "key-derivation-name"), "PBKDF2")
        derivation.set(qn("manifest", "salt"), "AAAAAAAAAAAAAAAAAAAAAA==")
        derivation.set(qn("manifest", "iteration-count"), "1024")
        derivation.set(qn("manifest", "key-size"), "16")
    # The independent oracle is the unmodified bundled OASIS manifest grammar. It does
    # not inspect body XML, decrypt bytes or establish that these invented keys work.
    grammar = Path(odfa11y.odf.__file__).parent / "schemas/OpenDocument-v1.4-manifest-schema.rng"
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    validator = etree.RelaxNG(etree.parse(str(grammar), parser))
    assert validator.validate(manifest), str(validator.error_log)
    paths = [
        node.get(qn("manifest", "full-path"))
        for node in manifest
        if node.tag == qn("manifest", "file-entry")
    ]
    assert len(paths) == len(set(paths))
    serialized = etree.tostring(manifest)
    assert b"<m:manifest" in serialized
    return serialized


@pytest.mark.parametrize("member", ["content.xml", "opaque.bin"])
@pytest.mark.parametrize("declaration", ["encryption-data", "encrypted-key"])
def test_manifest_encryption_stops_inspection_planning_edits_and_native_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str, declaration: str
) -> None:
    source = make_minimal_odt(tmp_path / "encrypted.odt")
    storage = PackageStorage(source)
    manifest = encrypted_manifest(storage, member, declaration)
    storage.write_member("META-INF/manifest.xml", manifest)
    storage.write_member(member, b"invented ciphertext, not XML")
    storage.save(source)
    original = source.read_bytes()
    with zipfile.ZipFile(source) as archive:
        assert all(not member.flag_bits & 1 for member in archive.infolist())
    calls = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        calls.append((_args, _kwargs))
        pytest.fail("guarded operation/native invocation executed for encrypted input")

    monkeypatch.setattr(SetMetadata, "apply", forbidden)
    monkeypatch.setattr("odfa11y.pipeline.native.export_pdfua", forbidden)
    report, template = prepare_plan(source)
    assert [finding.rule_id for finding in report.findings] == ["PKG009"]
    assert template is None
    destination = tmp_path / "out.odt"
    destination.write_bytes(b"existing destination")
    for operations in ([], [SetMetadata(title="Changed")], [SetMetadata()]):
        for dry_run in (False, True):
            with pytest.raises(PackageError, match="Protected"):
                execute_operations(source, destination, operations, dry_run=dry_run)
    with pytest.raises(PackageError, match="encrypted"):
        export_document(source, tmp_path / "out.pdf")
    assert calls == []
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"existing destination"
    assert not (tmp_path / "out.pdf").exists()


def test_malformed_manifest_is_not_protection_absence(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "bad.odt")
    storage = PackageStorage(source)
    storage.write_member("META-INF/manifest.xml", b"<broken")
    storage.save(source)
    report = audit_odf(source)
    assert [finding.rule_id for finding in report.findings] == ["XML001"]
    with pytest.raises(PackageError, match="malformed"):
        execute_operations(source, tmp_path / "out.odt", [])


def test_unsigned_fixture_remains_supported(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    facts = OdfDocument.open(source).protection
    assert not facts.signatures
    assert not facts.encrypted
    assert facts.malformed_manifest is None
    assert execute_operations(source, tmp_path / "out.odt", [SetMetadata(title="Reviewed")]).changed


def test_well_formed_non_manifest_root_is_not_protection_absence(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "wrong-root.odt")
    storage = PackageStorage(source)
    storage.write_member("META-INF/manifest.xml", b"<not-a-manifest/>")
    storage.save(source)
    report = audit_odf(source)
    assert [finding.rule_id for finding in report.findings] == ["XML001"]
    with pytest.raises(PackageError, match="malformed"):
        execute_operations(source, tmp_path / "out.odt", [])
