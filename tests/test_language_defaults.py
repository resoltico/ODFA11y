# SPDX-License-Identifier: MPL-2.0
"""Lossless language declarations and native default-channel persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.content import normalize_language, style_language
from odfa11y.external_tools import run_bounded
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.remediation import SetMetadata

from .documents import make_flat, make_package
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


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
    SetMetadata(language="en-GB").apply(document)
    default = document.edit(Part.STYLES).find("office:styles/style:default-style", NS)
    assert default is not None
    props = default.find("style:text-properties", NS)
    assert props is not None
    props.set(qn("style", "rfc-language-tag"), "de-1996")
    props.set(qn("fo", "script"), "Cyrl")
    operation = SetMetadata(language=tag)
    assert operation.apply(document)[0].status is Status.APPLIED
    for channel in range(3):
        assert style_language(document, "paragraph", channel) == tag
    destination = tmp_path / ("changed.fodt" if flat else "changed.odt")
    document.save(destination)
    report = audit_odf(destination, schema=True)
    assert report.metadata["language"] == tag
    assert "ODF900" not in {finding.rule_id for finding in report.findings}
    assert all(outcome.status is Status.UNCHANGED for outcome in operation.apply(document))
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
    assert (
        SetMetadata(title="Chosen title", language=tag).apply(document)[0].status is Status.FAILED
    )
    assert etree.tostring(document.tree(Part.META)) == before
    with pytest.raises(ValueError, match="Invalid language"):
        normalize_language(tag)


@pytest.mark.parametrize("target", ["styles", "default-style", "text-properties"])
def test_ambiguous_defaults_fail_before_metadata_changes(tmp_path: Path, target: str) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    SetMetadata(language="en-GB").apply(document)
    styles = document.edit(Part.STYLES)
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
    result = SetMetadata(title="Chosen title", language="en-GB").apply(document)
    assert result[0].status is Status.FAILED
    assert "Ambiguous" in result[0].message
    assert etree.tostring(document.tree(Part.META)) == before


@pytest.mark.integration
@pytest.mark.parametrize(
    ("tag", "native_tag"),
    [
        ("sr-Latn-RS", "sr-Latn-RS"),
        ("zh-Hant-TW", "zh-TW"),
        ("es-419", "es-419"),
        ("de-1996", "de-1996"),
        ("en-u-ca-buddhist", "en-u-ca-buddhist"),
        ("x-private", "x-private"),
        ("i-klingon", "tlh"),
        ("zh-cmn-Hans-CN", "cmn-Hans-CN"),
        ("sl-rozaj-biske-1994", "sl-rozaj-biske-1994"),
    ],
)
def test_native_reload_measures_three_defaults_and_preserves_named_override(
    tmp_path: Path, external_tool: Callable[..., str], tag: str, native_tag: str
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    SetMetadata(language="en-GB").apply(document)
    container = document.edit(Part.STYLES).find("office:styles", NS)
    assert container is not None
    named = etree.SubElement(container, qn("style", "style"))
    named.set(qn("style", "name"), "AuthoredLanguage")
    named.set(qn("style", "family"), "paragraph")
    props = etree.SubElement(named, qn("style", "text-properties"))
    props.set(qn("fo", "language"), "fr")
    props.set(qn("fo", "country"), "FR")
    paragraph = document.edit(Part.CONTENT).find(".//text:p", NS)
    assert paragraph is not None
    paragraph.set(qn("text", "style-name"), "AuthoredLanguage")
    assert SetMetadata(language=tag).apply(document)[0].status is Status.APPLIED
    source_props = document.tree(Part.STYLES).find(
        "office:styles/style:default-style/style:text-properties", NS
    )
    assert source_props is not None
    if tag == "zh-Hant-TW":
        assert source_props.get(qn("fo", "script")) == "Hant"
        for channel in ("asian", "complex"):
            assert source_props.get(qn("style", "script-" + channel)) == "Hant"
    elif tag in {"i-klingon", "zh-cmn-Hans-CN"}:
        for suffix in ("", "-asian", "-complex"):
            assert source_props.get(qn("style", "rfc-language-tag" + suffix)) == tag
    source = tmp_path / "language.odt"
    document.save(source)
    converted = tmp_path / "converted"
    converted.mkdir()
    result = run_bounded(
        [
            soffice,
            "--headless",
            f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}",
            "--convert-to",
            "fodt",
            "--outdir",
            str(converted),
            str(source),
        ],
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    reloaded = OdfDocument.open(converted / "language.fodt")
    for channel in range(3):
        assert style_language(reloaded, "paragraph", channel) == native_tag
    if tag == "zh-Hant-TW":
        # Negative capability control: source keeps Hant, but the native exporter drops it.
        native_props = reloaded.tree(Part.STYLES).find(
            "office:styles/style:default-style/style:text-properties", NS
        )
        assert native_props is not None
        assert native_props.get(qn("fo", "script")) is None
        for channel in ("asian", "complex"):
            assert native_props.get(qn("style", "script-" + channel)) is None
    override = reloaded.tree(Part.STYLES).find(
        "office:styles/style:style[@style:name='AuthoredLanguage']/style:text-properties", NS
    )
    assert override is not None
    assert override.get(qn("fo", "language")) == "fr"
    assert override.get(qn("fo", "country")) == "FR"


@pytest.mark.parametrize(
    ("kind", "family"),
    [
        ("text", "paragraph"),
        ("spreadsheet", "table-cell"),
        ("graphics", "paragraph"),
        ("presentation", "paragraph"),
        ("image", "paragraph"),
    ],
)
def test_family_defaults_keep_authored_named_and_automatic_overrides(
    tmp_path: Path, kind: str, family: str
) -> None:
    document = OdfDocument.open(make_package(tmp_path, kind))
    SetMetadata(language="en-GB").apply(document)
    container = document.edit(Part.STYLES).find("office:styles", NS)
    assert container is not None
    named = etree.SubElement(container, qn("style", "style"))
    named.set(qn("style", "name"), "ReviewedLanguage")
    named.set(qn("style", "family"), family)
    props = etree.SubElement(named, qn("style", "text-properties"))
    props.set(qn("style", "rfc-language-tag"), "de-1996")
    content = document.edit(Part.CONTENT)
    automatic = etree.Element(qn("office", "automatic-styles"))
    content.getroot().insert(0, automatic)
    automatic.append(etree.fromstring(etree.tostring(named)))
    authored_before = etree.tostring(named), etree.tostring(automatic)
    result = SetMetadata(language="sr-Latn-RS").apply(document)
    assert result[0].status is Status.APPLIED
    for channel in range(3):
        assert style_language(document, family, channel) == "sr-Latn-RS"
    assert (etree.tostring(named), etree.tostring(automatic)) == authored_before
