# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for language defaults."""

from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.concepts import style_language
from odfa11y.decisions.edit import Status
from odfa11y.native.process import run_bounded
from odfa11y.odf import NS, OdfDocument, Part, qn
from tests.fixtures.answers import metadata_input
from tests.fixtures.writer import make_minimal_odt
lazy from tests.fixtures.answers import apply_in_memory


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
    apply_in_memory(document, metadata_input(language="en-GB"))
    container = document.tree(Part.STYLES).find("office:styles", NS)
    assert container is not None
    named = etree.SubElement(container, qn("style", "style"))
    named.set(qn("style", "name"), "AuthoredLanguage")
    named.set(qn("style", "family"), "paragraph")
    props = etree.SubElement(named, qn("style", "text-properties"))
    props.set(qn("fo", "language"), "fr")
    props.set(qn("fo", "country"), "FR")
    paragraph = document.tree(Part.CONTENT).find(".//text:p", NS)
    assert paragraph is not None
    paragraph.set(qn("text", "style-name"), "AuthoredLanguage")
    assert apply_in_memory(document, metadata_input(language=tag))[0].status is Status.APPLIED
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
