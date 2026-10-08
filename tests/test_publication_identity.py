# SPDX-License-Identifier: MPL-2.0
"""Published bytes, structured diagnostics and recorded hashes agree."""

from __future__ import annotations

import hashlib
import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

import pytest
from lxml import etree

from odfa11y.evidence import Redactor, check_bundle, write_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, PackageStorage
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .documents import make_flat
from .fixtures import make_minimal_odt
from .test_evidence import record


@pytest.mark.parametrize("suffix", [".xml", ".fodt", ".odt"])
def test_published_document_is_the_remediated_payload(tmp_path: Path, suffix: str) -> None:
    source = (
        make_minimal_odt(tmp_path / "source.odt")
        if suffix == ".odt"
        else make_flat(tmp_path, "text").rename(tmp_path / f"source{suffix}")
    )
    if suffix != ".odt":
        source.write_bytes(
            source.read_bytes().replace(b"</text:p>", b" /private/person/file</text:p>", 1)
        )
    target = tmp_path / "bundle"
    result = run_pipeline(source, [], FidelityPolicy(), target, PipelineOptions(profile="inspect"))
    delivered = target / f"remediated{suffix}"
    OdfDocument.open(delivered)
    assert delivered.read_bytes() == source.read_bytes()
    assert result.outputs[delivered.name] == hashlib.sha256(delivered.read_bytes()).hexdigest()
    assert check_bundle(target) == []


def test_structured_diagnostics_and_final_hashes(tmp_path: Path) -> None:
    xml = tmp_path / "report.xml"
    xml.write_text('<report path="/private/person/a&amp;b">C:\\Users\\Person\\f.pdf</report>')
    target = tmp_path / "bundle"
    write_bundle(target, record(), {"report.xml": xml}, Redactor(()), diagnostics={"report.xml"})
    root = etree.parse(target / "report.xml").getroot()
    assert root.get("path") == "<path>/a&b"
    assert root.text == "<path>/f.pdf"
    published = json.loads((target / "run.json").read_text())
    assert (
        published["outputs"]["report.xml"]
        == hashlib.sha256((target / "report.xml").read_bytes()).hexdigest()
    )
    assert check_bundle(target) == []


def test_unwritable_publication_has_no_partial_directory(tmp_path: Path) -> None:
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o500)
    source = tmp_path / "artifact"
    source.write_bytes(b"payload")
    try:
        if os.access(parent, os.W_OK):
            pytest.skip("The platform does not enforce POSIX directory modes for this user")
        with pytest.raises(PermissionError):
            write_bundle(parent / "bundle", record(), {"artifact": source}, Redactor(()))
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)


def test_accepted_package_with_xml_suffix_is_copied_unchanged(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.xml")
    target = tmp_path / "bundle"
    result = run_pipeline(source, [], FidelityPolicy(), target, PipelineOptions(profile="inspect"))
    OdfDocument.open(target / "remediated.xml")
    assert (target / "remediated.xml").read_bytes() == source.read_bytes()
    assert result.passed


def test_flat_document_preserves_declared_encoding(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text")
    source.write_bytes(
        source
        .read_bytes()
        .replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"')
        .replace(b'encoding="utf-8"', b'encoding="ISO-8859-1"')
        .replace(b"</text:p>", b" caf\xe9</text:p>", 1)
    )
    target = tmp_path / "bundle"
    result = run_pipeline(source, [], FidelityPolicy(), target, PipelineOptions(profile="inspect"))
    assert result.passed
    delivered = target / f"remediated{source.suffix}"
    OdfDocument.open(delivered)
    assert delivered.read_bytes() == source.read_bytes()


@pytest.mark.integration
def test_native_published_artifact_syntax_content_and_identity(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    package = PackageStorage(source)
    authored = str(tmp_path / "authored-file").encode()
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"Body paragraph.", authored)
    )
    package.save(source)
    target = tmp_path / "bundle"
    result = run_pipeline(
        source,
        [],
        FidelityPolicy(),
        target,
        PipelineOptions(
            profile="production",
            soffice=external_tool("soffice", "libreoffice"),
            verapdf_path=external_tool("verapdf"),
        ),
    )
    assert result.passed, result.as_dict()
    delivered = OdfDocument.open(target / "remediated.odt")
    assert authored in delivered.storage.read("content.xml")
    assert (target / "remediated.odt").read_bytes() == source.read_bytes()
    etree.parse(target / "verapdf.xml")
    published = json.loads((target / "run.json").read_text())
    manifest = json.loads((target / "manifest.json").read_text())["files"]
    assert result.outputs == published["outputs"]
    for name, digest in manifest.items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
    for name, digest in result.outputs.items():
        assert digest == manifest[name]
    assert check_bundle(target) == []
