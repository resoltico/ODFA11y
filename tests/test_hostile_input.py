# SPDX-License-Identifier: MPL-2.0
"""Inputs that are malformed, adversarial or merely unusual must not crash or corrupt output."""

from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING, Unpack

import pypdfium2
import pytest

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.errors import PackageError, RemediationError, ToolFailedError
from odfa11y.families.text import HeaderRows, LinkifyAddresses, MarkHeaderRows, RemoveEmptySpacers
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.fidelity import compare as compare_module
from odfa11y.odf import OdfDocument, PackageStorage, Part, select_elements
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, SetOdfVersion, remediate

from .fixtures import make_minimal_odt
from .pdf_fixtures import text_pdf

if TYPE_CHECKING:
    from pathlib import Path

    from .fixtures import Features

CENTRAL_DIRECTORY_SIGNATURE = b"PK\x01\x02"
ENCRYPTED_FLAG_OFFSET = 8
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions and modes")


def with_body(tmp_path: Path, body: bytes, **features: Unpack[Features]) -> Path:
    """Insert markup at the start of the document body.

    Returns
    -------
    Path
        The rewritten document.

    """
    package = PackageStorage(make_minimal_odt(tmp_path / "base.odt", **features))
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + body, 1),
    )
    path = tmp_path / "body.odt"
    package.save(path)
    return path


def test_malformed_optional_members_do_not_abort_the_audit_or_remediation(tmp_path: Path) -> None:
    package = PackageStorage(make_minimal_odt(tmp_path / "base.odt"))
    package.write_member("settings.xml", b"<not-closed")
    broken = tmp_path / "broken.odt"
    package.save(broken)
    report = audit_odf(broken, schema=True)
    assert "XML001" in {f.rule_id for f in report.findings}
    result = remediate(broken, tmp_path / "out.odt", [SetMetadata(title="Still works")])
    assert result.changed


def test_zip_encrypted_members_are_an_invalid_package_not_a_crash(tmp_path: Path) -> None:
    data = bytearray(make_minimal_odt(tmp_path / "base.odt").read_bytes())
    position = data.find(CENTRAL_DIRECTORY_SIGNATURE)
    while position != -1:
        data[position + ENCRYPTED_FLAG_OFFSET] |= 0x1
        position = data.find(CENTRAL_DIRECTORY_SIGNATURE, position + 1)
    encrypted = tmp_path / "encrypted.odt"
    encrypted.write_bytes(bytes(data))
    with pytest.raises(PackageError):
        PackageStorage(encrypted)
    assert {f.rule_id for f in audit_odf(encrypted).findings} == {"PKG000"}


ANNOTATED = (
    b'<text:p text:style-name="Body">See <office:annotation xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b"<dc:creator>jane@example.test</dc:creator><text:p>Note https://example.test/note</text:p>"
    b"</office:annotation> and https://example.test/real<!-- https://example.test/comment -->"
    b" then qa@example.test"
    b'<draw:frame draw:name="F"><svg:desc>https://example.test/alt</svg:desc></draw:frame></text:p>'
)


def test_linkification_touches_only_prose_not_annotations_descriptions_or_comments(
    tmp_path: Path,
) -> None:
    source = with_body(tmp_path, ANNOTATED)
    audited = [f for f in audit_odf(source).findings if f.rule_id == "TXT030"]
    assert sorted(f.details["text"] for f in audited) == [
        "https://example.test/note",
        "https://example.test/real",
        "qa@example.test",
    ]
    document = OdfDocument.open(source)
    (outcome,) = LinkifyAddresses().apply(document)
    assert (outcome.status, outcome.count) == (Status.APPLIED, 3)
    content = document.tree(Part.CONTENT)
    assert not select_elements(content, "//svg:desc/text:a | //dc:creator/text:a")
    links = select_elements(content, "//text:a")
    assert sorted(link.text or "" for link in links) == [
        "https://example.test/note",
        "https://example.test/real",
        "qa@example.test",
    ]
    assert audit_odf(source).findings  # the original is untouched
    assert LinkifyAddresses().apply(document)[0].status is Status.UNCHANGED


@pytest.mark.parametrize(
    "marker",
    [
        b"<text:change-start text:change-id='c'/>",
        b"<text:change text:change-id='c'/>",
        b"<office:annotation-end office:name='a'/>",
        b"<text:page-number/>",
        b"<text:sequence/>",
        b"<text:alphabetical-index-mark text:string-value='x'/>",
        b"<text:user-index-mark text:string-value='x' text:index-name='n'/>",
    ],
)
def test_paragraphs_with_markers_or_fields_are_never_removed_as_spacers(
    tmp_path: Path, marker: bytes
) -> None:
    body = b'<text:p text:style-name="Body" xml:id="marked">' + marker + b"</text:p>"
    document = OdfDocument.open(with_body(tmp_path, body))
    RemoveEmptySpacers().apply(document)
    assert select_elements(document.tree(Part.CONTENT), "//*[@xml:id='marked']")


def test_audit_and_remediation_agree_on_what_a_spacer_is(tmp_path: Path) -> None:
    listed = (
        b'<text:list><text:list-item><text:p text:style-name="Body"/></text:list-item></text:list>'
    )
    source = with_body(tmp_path, listed)
    finding = next(f for f in audit_odf(source).findings if f.rule_id == "TXT040")
    (outcome,) = RemoveEmptySpacers().apply(OdfDocument.open(source))
    assert finding.details["count"] == outcome.count == 1  # the list item's paragraph is neither


def test_a_relabel_from_a_version_without_a_schema_must_yield_a_valid_document(
    tmp_path: Path,
) -> None:
    valid = make_minimal_odt(tmp_path / "v12.odt", version="1.2", with_data_table=True)
    result = remediate(valid, tmp_path / "out.odt", [SetOdfVersion("1.4")])
    assert result.schema_check.startswith("valid against ODF 1.4")
    package = PackageStorage(valid)
    package.write_member(
        "content.xml", package.read("content.xml").replace(b"<table:table-column/>", b"")
    )
    invalid = tmp_path / "invalid.odt"
    package.save(invalid)
    with pytest.raises(RemediationError, match="must validate"):
        remediate(invalid, tmp_path / "never.odt", [SetOdfVersion("1.4")])
    assert not (tmp_path / "never.odt").exists()


def test_duplicate_table_names_are_ambiguous_and_fail(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "base.odt", with_data_table=True)
    package = PackageStorage(source)
    content = package.read("content.xml")
    start, end = (
        content.index(b"<table:table "),
        content.index(b"</table:table>") + len(b"</table:table>"),
    )
    package.write_member("content.xml", content[:end] + content[start:end] + content[end:])
    twin = tmp_path / "twin.odt"
    package.save(twin)
    (outcome,) = MarkHeaderRows({"Data": HeaderRows(1)}).apply(OdfDocument.open(twin))
    assert outcome.status is Status.FAILED
    assert "must be unique" in outcome.message


@POSIX_ONLY
def test_a_non_executable_soffice_fails_the_stage_and_still_publishes_evidence(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o600)
    record = run_pipeline(
        source, [], FidelityPolicy(), tmp_path / "out", PipelineOptions(soffice=str(fake))
    )
    assert record.failed_stage == "export-source"
    assert (tmp_path / "out" / "run.json").is_file()


def test_a_renderer_failure_is_a_tool_error_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = text_pdf(tmp_path / "a.pdf", [["Some text"]])

    def refuse(*_args: object, **_kwargs: object) -> object:
        message = "cannot load document"
        raise pypdfium2.PdfiumError(message)

    monkeypatch.setattr(compare_module.pypdfium2, "PdfDocument", refuse)
    with pytest.raises(ToolFailedError, match="Cannot render"):
        compare_pdfs(pdf, pdf, FidelityPolicy())


@POSIX_ONLY
def test_published_outputs_honour_the_umask_instead_of_being_owner_only(tmp_path: Path) -> None:
    previous = os.umask(0o022)
    try:
        source = make_minimal_odt(tmp_path / "doc.odt")
        record = run_pipeline(
            source, [], FidelityPolicy(), tmp_path / "out", PipelineOptions(soffice="missing")
        )
        remediated = tmp_path / "remediated.odt"
        remediate(source, remediated, [SetMetadata(title="Modes")])
    finally:
        os.umask(previous)
    assert record.failed_stage == "export-source"
    assert stat.S_IMODE(remediated.stat().st_mode) == 0o644
    bundle = tmp_path / "out"
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o755
    assert stat.S_IMODE((bundle / "run.json").stat().st_mode) == 0o644
