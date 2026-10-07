# SPDX-License-Identifier: MPL-2.0
"""Test remediate for ODF accessibility workflows."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from odfa11y.audit import audit_odt
from odfa11y.odf import OdtPackage, qn, select_elements
from odfa11y.remediation import AltText, RemediationOptions, remediate_odt

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_remediation_fixes_safe_structural_issues(tmp_path: Path) -> None:
    source = make_minimal_odt(
        tmp_path / "source.odt",
        version="1.3",
        title="Old title",
        language="en-US",
        with_plain_email=True,
        with_data_table=True,
        with_image_without_alt=True,
    )
    dest = tmp_path / "out.odt"
    options = RemediationOptions(
        target_version="1.4",
        title="New title",
        language="en-GB",
        linkify_plain_addresses=True,
        table_header_rows={"Data": 1},
        alt_text={"Logo": AltText(title="Example logo", description="Decorative sample logo")},
    )
    result = remediate_odt(source, dest, options=options)
    assert result.destination == dest

    report = audit_odt(dest)
    assert report.error_count == 0
    assert not any(i.rule_id in {"LNK001", "TBL002", "IMG001", "ODF001"} for i in report.issues)
    assert report.metadata["title"] == "New title"
    assert report.metadata["language"] == "en-GB"

    package = OdtPackage(dest)
    content = package.parse_xml("content.xml")
    links = select_elements(content, "//text:a")
    assert len(links) == 1
    assert links[0].get(qn("xlink", "href")) == "mailto:test@example.com"
    assert (
        len(
            select_elements(
                content, "//table:table[@table:name='Data']/table:table-header-rows/table:table-row"
            )
        )
        == 1
    )


def test_rewritten_package_keeps_odf_mimetype_invariant(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    dest = tmp_path / "out.odt"
    remediate_odt(source, dest, options=RemediationOptions(title="Updated"))
    with zipfile.ZipFile(dest) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/vnd.oasis.opendocument.text"


def test_linkify_preserves_trailing_punctuation_and_balanced_parentheses(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    package = OdtPackage(source)
    tree = package.parse_xml("content.xml")
    paragraph = select_elements(tree, "//text:p[1]")[0]
    paragraph.text = "See https://example.test/a_(b). Then email qa@example.test."
    package.write_xml("content.xml", tree)
    package.save(source)

    dest = tmp_path / "out.odt"
    remediate_odt(
        source,
        dest,
        options=RemediationOptions(linkify_plain_addresses=True),
    )
    out = OdtPackage(dest).parse_xml("content.xml")
    links = select_elements(out, "//text:a")
    assert [link.get(qn("xlink", "href")) for link in links] == [
        "https://example.test/a_(b)",
        "mailto:qa@example.test",
    ]
    visible = "".join(select_elements(out, "//text:p")[0].itertext())
    assert visible == "See https://example.test/a_(b). Then email qa@example.test."
