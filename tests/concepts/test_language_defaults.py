# SPDX-License-Identifier: MPL-2.0
"""Lossless language declarations and native default-channel persistence."""

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.concepts import style_language
from odfa11y.decisions.edit import Status
from odfa11y.errors import PlanError
from odfa11y.language_tags import normalize_language
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.report import FactKeys
from tests.fixtures.answers import metadata_input
from tests.fixtures.documents import make_flat, make_package
lazy from tests.fixtures.answers import apply_in_memory


@pytest.mark.parametrize(
    "tag",
    [
        "en-GB",
        "sr-Latn-RS",
        "zh-Hant-TW",
        "es-419",
        "de-1996",
        "en-u-ca-buddhist",
        "x-private",
        "i-klingon",
        "en-GB-oed",
        "zh-cmn-Hans-CN",
        "sl-rozaj-biske-1994",
        "en-a-test-x-foo",
    ],
)
@pytest.mark.parametrize("flat", [False, True])
def test_language_preserves_all_subtags_and_replaces_stale_defaults(
    tmp_path: Path, tag: str, *, flat: bool
) -> None:
    source = (make_flat if flat else make_package)(tmp_path, "text")
    document = OdfDocument.open(source)
    apply_in_memory(document, metadata_input(language="en-GB"))
    default = document.tree(Part.STYLES).find("office:styles/style:default-style", NS)
    assert default is not None
    props = default.find("style:text-properties", NS)
    assert props is not None
    props.set(qn("style", "rfc-language-tag"), "de-1996")
    props.set(qn("fo", "script"), "Cyrl")
    operation = metadata_input(language=tag)
    assert apply_in_memory(document, operation)[0].status is Status.APPLIED
    for channel in range(3):
        assert style_language(document, "paragraph", channel) == tag
    destination = tmp_path / ("changed.fodt" if flat else "changed.odt")
    document.save(destination)
    report = audit_odf(destination, schema=True)
    assert report.facts[FactKeys.DOCUMENT_LANGUAGE] == tag
    assert "SCHEMA001" not in {finding.rule_id for finding in report.findings}
    assert all(
        outcome.status is Status.UNCHANGED for outcome in apply_in_memory(document, operation)
    )
    props = document.tree(Part.STYLES).find(
        "office:styles/style:default-style/style:text-properties", NS
    )
    assert props is not None
    if tag == "sr-Latn-RS":
        # Independent XML oracle: every standard channel includes language, script and country.
        assert props.get(qn("fo", "language")) == "sr"
        assert props.get(qn("fo", "script")) == "Latn"
        assert props.get(qn("fo", "country")) == "RS"
        for channel in ("asian", "complex"):
            assert props.get(qn("style", "language-" + channel)) == "sr"
            assert props.get(qn("style", "script-" + channel)) == "Latn"
            assert props.get(qn("style", "country-" + channel)) == "RS"
        assert props.get(qn("style", "rfc-language-tag")) is None
    if tag == "en-u-ca-buddhist":
        assert props.get(qn("style", "rfc-language-tag")) == tag
        assert props.get(qn("fo", "country")) is None
        assert props.get(qn("fo", "script")) is None


@pytest.mark.parametrize(
    "tag",
    [
        "en-u",
        "en-x",
        "en-a-foo-a-bar",
        "sl-rozaj-rozaj",
        "en--GB",
        "en-1234-1234",
        "en-GB-Latn",
        "i-unknown",
    ],
)
def test_malformed_tags_fail_before_other_metadata_changes(tmp_path: Path, tag: str) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    before = etree.tostring(document.tree(Part.META))
    with pytest.raises(PlanError, match="language"):
        apply_in_memory(document, metadata_input(title="Chosen title", language=tag))
    assert etree.tostring(document.tree(Part.META)) == before
    with pytest.raises(ValueError, match="Invalid language"):
        normalize_language(tag)


@pytest.mark.parametrize("target", ["styles", "default-style", "text-properties"])
def test_ambiguous_defaults_fail_before_metadata_changes(tmp_path: Path, target: str) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    apply_in_memory(document, metadata_input(language="en-GB"))
    styles = document.tree(Part.STYLES)
    node = styles.find(
        "office:styles" if target == "styles" else "office:styles/style:default-style", NS
    )
    assert node is not None
    if target == "text-properties":
        node = node.find("style:text-properties", NS)
    assert node is not None
    assert node.getparent() is not None
    parent = node.getparent()
    assert parent is not None
    parent.append(etree.fromstring(etree.tostring(node)))
    before = etree.tostring(document.tree(Part.META))
    result = apply_in_memory(document, metadata_input(title="Chosen title", language="en-GB"))
    assert result[0].status is Status.FAILED
    assert "Ambiguous" in result[0].message
    assert etree.tostring(document.tree(Part.META)) == before


@pytest.mark.parametrize(
    ("kind", "family"),
    [
        ("text", "paragraph"),
        ("spreadsheet", "table-cell"),
        ("drawing", "paragraph"),
        ("presentation", "paragraph"),
        ("image", "paragraph"),
    ],
)
def test_family_defaults_keep_authored_named_and_automatic_overrides(
    tmp_path: Path, kind: str, family: str
) -> None:
    document = OdfDocument.open(make_package(tmp_path, kind))
    apply_in_memory(document, metadata_input(language="en-GB"))
    container = document.tree(Part.STYLES).find("office:styles", NS)
    assert container is not None
    named = etree.SubElement(container, qn("style", "style"))
    named.set(qn("style", "name"), "ReviewedLanguage")
    named.set(qn("style", "family"), family)
    props = etree.SubElement(named, qn("style", "text-properties"))
    props.set(qn("style", "rfc-language-tag"), "de-1996")
    content = document.tree(Part.CONTENT)
    automatic = etree.Element(qn("office", "automatic-styles"))
    content.getroot().insert(0, automatic)
    automatic.append(etree.fromstring(etree.tostring(named)))
    authored_before = etree.tostring(named), etree.tostring(automatic)
    result = apply_in_memory(document, metadata_input(language="sr-Latn-RS"))
    assert result[0].status is Status.APPLIED
    for channel in range(3):
        assert style_language(document, family, channel) == "sr-Latn-RS"
    assert (etree.tostring(named), etree.tostring(automatic)) == authored_before
