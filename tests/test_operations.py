# SPDX-License-Identifier: MPL-2.0
"""Each operation: applies once, then reports unchanged; every failure is explicit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

import pytest
from lxml import etree

from odfa11y.odf import OdtDocument, qn, select_elements, validate
from odfa11y.remediation import (
    AltText,
    LinkifyAddresses,
    MarkHeaderRows,
    NormalizeSpacing,
    RemoveEmptySpacers,
    SetAltText,
    SetMetadata,
    SetOdfVersion,
    Status,
    clone_style_name,
)

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.remediation import (
        Operation,
    )

    from .fixtures import Features


def run(operation: Operation, document: OdtDocument) -> tuple[Status, ...]:
    """Apply an operation and return its statuses.

    Returns
    -------
    tuple[Status, ...]
        The status of each outcome.

    """
    return tuple(outcome.status for outcome in operation.apply(document))


def document(tmp_path: Path, *, version: str = "1.4", **features: Unpack[Features]) -> OdtDocument:
    """Open a synthetic document with the given features.

    Returns
    -------
    OdtDocument
        A fresh document.

    """
    return OdtDocument.open(make_minimal_odt(tmp_path / "doc.odt", version=version, **features))


def assert_valid(doc: OdtDocument) -> None:
    """Fail if the document no longer validates against its bundled schema."""
    assert validate(doc).violations == {}


@pytest.mark.parametrize("version", ["1.3", "1.4"])
def test_odf_version_is_applied_once_and_stays_valid(tmp_path: Path, version: str) -> None:
    doc = document(tmp_path, version="1.3" if version == "1.4" else "1.4")
    operation = SetOdfVersion(version)
    assert run(operation, doc) == (Status.APPLIED,)
    assert run(operation, doc) == (Status.UNCHANGED,)
    assert_valid(doc)


def test_odf_version_without_a_bundled_schema_fails(tmp_path: Path) -> None:
    assert run(SetOdfVersion("1.2"), document(tmp_path)) == (Status.FAILED,)


def test_metadata_is_applied_once_and_language_reaches_both_places(tmp_path: Path) -> None:
    doc = document(tmp_path)
    operation = SetMetadata(title=" New title ", description="About", language="fr-CA")
    assert run(operation, doc) == (Status.APPLIED,) * 3
    assert run(operation, doc) == (Status.UNCHANGED,) * 3
    assert (
        doc.tree("meta.xml").findtext(
            ".//dc:title", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}
        )
        == "New title"
    )
    props = select_elements(doc.tree("styles.xml"), "//style:default-style/style:text-properties")[
        0
    ]
    assert (props.get(qn("fo", "language")), props.get(qn("fo", "country"))) == ("fr", "CA")
    assert_valid(doc)


@pytest.mark.parametrize("tag", ["", "x", "en GB", "12-34"])
def test_invalid_language_tags_fail(tmp_path: Path, tag: str) -> None:
    assert run(SetMetadata(language=tag), document(tmp_path)) == (Status.FAILED,)


def test_alt_text_is_ordered_for_the_schema_applied_once_and_unmatched_keys_fail(
    tmp_path: Path,
) -> None:
    doc = document(tmp_path, with_image_without_alt=True)
    entries = {"Logo": AltText("Title", "Description"), "Missing": AltText("x")}
    assert run(SetAltText(entries), doc) == (Status.APPLIED, Status.FAILED)
    assert_valid(doc)
    assert run(SetAltText({"Logo": AltText("Title", "Description")}), doc) == (Status.UNCHANGED,)
    assert run(SetAltText({"logo.svg": AltText(description="By file name")}), doc) == (
        Status.APPLIED,
    )
    assert_valid(doc)


def test_header_rows_apply_once_and_conflicts_fail(tmp_path: Path) -> None:
    doc = document(tmp_path, with_data_table=True)
    assert run(MarkHeaderRows({"Data": 1}), doc) == (Status.APPLIED,)
    assert run(MarkHeaderRows({"Data": 1}), doc) == (Status.UNCHANGED,)
    assert run(MarkHeaderRows({"Data": 2}), doc) == (Status.FAILED,)
    assert_valid(doc)


def test_header_rows_fail_for_unknown_tables_and_too_many_rows(tmp_path: Path) -> None:
    doc = document(tmp_path, with_data_table=True)
    assert run(MarkHeaderRows({"Nope": 1}), doc) == (Status.FAILED,)
    assert run(MarkHeaderRows({"Data": 9}), doc) == (Status.FAILED,)


def test_linkify_applies_once_and_keeps_the_document_valid(tmp_path: Path) -> None:
    doc = document(tmp_path, with_plain_email=True)
    assert run(LinkifyAddresses(), doc) == (Status.APPLIED,)
    assert run(LinkifyAddresses(), doc) == (Status.UNCHANGED,)
    assert_valid(doc)


def test_spacer_removal_applies_once(tmp_path: Path) -> None:
    doc = document(tmp_path, add_blank_body_paragraph=True)
    assert run(RemoveEmptySpacers(), doc) == (Status.APPLIED,)
    assert run(RemoveEmptySpacers(), doc) == (Status.UNCHANGED,)
    assert [p.text for p in select_elements(doc.tree("content.xml"), "//text:p")] == [
        "Body paragraph."
    ]


@pytest.mark.parametrize("marker", ["draw", "bookmark", "tab", "break", "master", "table", "list"])
def test_spacer_removal_retains_semantically_protected_paragraphs(
    tmp_path: Path, marker: str
) -> None:
    doc = document(tmp_path, add_blank_body_paragraph=True)
    paragraph = select_elements(doc.tree("content.xml"), "//text:p[not(text())]")[0]
    paragraph.set("{http://www.w3.org/XML/1998/namespace}id", "protected")
    _protect(doc, paragraph, marker)
    RemoveEmptySpacers().apply(doc)
    kept = select_elements(doc.tree("content.xml"), "//*[@xml:id='protected']")
    assert len(kept) == 1


def _protect(doc: OdtDocument, paragraph: etree._Element, marker: str) -> None:
    if marker in {"table", "list"}:
        namespace, tag = ("table", "table-cell") if marker == "table" else ("text", "list-item")
        parent = paragraph.getparent()
        assert parent is not None
        wrapper = etree.Element(qn(namespace, tag))
        parent.replace(paragraph, wrapper)
        wrapper.append(paragraph)
    elif marker in {"break", "master"}:
        style = select_elements(doc.edit("styles.xml"), "//style:style[@style:name='Body']")[0]
        properties = style.find("style:paragraph-properties", {"style": style.nsmap["style"]})
        assert properties is not None
        if marker == "break":
            properties.set(qn("fo", "break-before"), "page")
        else:
            style.set(qn("style", "master-page-name"), "Standard")
    else:
        child = {
            "draw": qn("draw", "frame"),
            "bookmark": qn("text", "bookmark"),
            "tab": qn("text", "tab"),
        }
        etree.SubElement(paragraph, child[marker])


def _spacing_document(tmp_path: Path) -> OdtDocument:
    doc = document(tmp_path)
    paragraphs = select_elements(doc.edit("content.xml"), "//text:p")
    paragraphs[0].set(qn("text", "style-name"), "Body")
    paragraphs[-1].set(qn("text", "style-name"), "BodyTight")
    return doc


def test_spacing_copies_reference_spacing_onto_a_derived_style_once(tmp_path: Path) -> None:
    doc = _spacing_document(tmp_path)
    operation = NormalizeSpacing("Body paragraph.", ("BodyTight",))
    assert run(operation, doc) == (Status.APPLIED,)
    last = select_elements(doc.tree("content.xml"), "//text:p[last()]")[0]
    assert last.get(qn("text", "style-name")) == clone_style_name("BodyTight")
    assert doc.catalog.spacing_signature(
        clone_style_name("BodyTight")
    ) == doc.catalog.spacing_signature("Body")
    assert doc.catalog.style("paragraph", "BodyTight") is not None
    assert run(operation, doc) == (Status.UNCHANGED,)


def test_spacing_follows_a_changed_reference_without_new_style_names(tmp_path: Path) -> None:
    doc = _spacing_document(tmp_path)
    NormalizeSpacing("Body paragraph.", ("BodyTight",)).apply(doc)
    paragraphs = select_elements(doc.edit("content.xml"), "//text:p")
    paragraphs[0].set(qn("text", "style-name"), "Heading1")
    outcome = NormalizeSpacing("Body paragraph.", ("BodyTight",)).apply(doc)[0]
    assert outcome.status is Status.APPLIED
    clones = [
        s
        for s in select_elements(doc.tree("content.xml"), "//style:style")
        if "A11ySpacing" in (s.get(qn("style", "name")) or "")
    ]
    assert len(clones) == 1


@pytest.mark.parametrize(
    "operation",
    [
        NormalizeSpacing("Nowhere", ("BodyTight",)),
        NormalizeSpacing("Body paragraph.", ("NoSuchStyle",)),
    ],
)
def test_spacing_failures_are_explicit(tmp_path: Path, operation: NormalizeSpacing) -> None:
    doc = _spacing_document(tmp_path)
    assert run(operation, doc) == (Status.FAILED,)


def test_operations_describe_themselves_in_json_compatible_values() -> None:
    described = SetAltText({"Logo": AltText("T", "D")}).as_dict()
    assert described == {
        "operation": "set_alt_text",
        "entries": {"Logo": {"title": "T", "description": "D"}},
    }
    assert MarkHeaderRows({"Data": 1}).as_dict() == {
        "operation": "mark_header_rows",
        "rows": {"Data": 1},
    }
    assert NormalizeSpacing("x", ("A",)).as_dict()["target_styles"] == ("A",)


def test_a_reference_style_without_spacing_cannot_be_copied(tmp_path: Path) -> None:
    doc = _spacing_document(tmp_path)
    select_elements(doc.edit("content.xml"), "//text:p")[0].set(qn("text", "style-name"), "Unknown")
    assert run(NormalizeSpacing("Body paragraph.", ("BodyTight",)), doc) == (Status.FAILED,)
