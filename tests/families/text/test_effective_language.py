# SPDX-License-Identifier: MPL-2.0
"""Target language follows scoped styles while retaining text and unrelated overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from lxml import etree

from odfa11y.families.text import SetTargetLanguages, TargetLanguage
from odfa11y.families.text.language import effective_languages
from odfa11y.families.text.language.effective import language_targets
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import assert_refused, execute_operations
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.adapter import Outcome

STYLES = (
    '<style:style style:name="Body" style:family="paragraph"><style:text-properties '
    'fo:language="en" fo:country="GB" style:language-asian="ja" '
    'style:language-complex="ar" fo:font-weight="bold"/></style:style>'
    '<style:style style:name="French" style:family="text"><style:text-properties '
    'fo:language="fr" fo:country="FR" fo:font-style="italic"/></style:style>'
)
BODY = (
    '<office:text><text:p text:style-name="Body">English '
    '<text:span text:style-name="French">Français</text:span> tail.</text:p></office:text>'
)


@pytest.mark.parametrize("make", [make_flat, make_package])
def test_effective_channels_and_isolated_target_edit(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    source = make(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    targets = language_targets(document)
    paragraph, inline = targets.values()
    assert effective_languages(document, paragraph) == ("en-GB", "ja", "ar")
    assert effective_languages(document, inline) == ("fr-FR", "ja", "ar")
    fingerprint = language_fingerprint(document, paragraph)
    target = next(iter(targets))
    operation = SetTargetLanguages({
        target: TargetLanguage(western="de-DE", fingerprint=fingerprint)
    })
    output = tmp_path / ("edited" + source.suffix)
    result = execute_operations(source, output, [operation])
    assert result.published, result.as_dict()
    after = OdfDocument.open(output)
    edited_paragraph, edited_inline = language_targets(after).values()
    assert effective_languages(after, edited_paragraph) == ("de-DE", "ja", "ar")
    assert effective_languages(after, edited_inline) == ("fr-FR", "ja", "ar")
    assert language_fingerprint(after, edited_paragraph) == fingerprint
    assert "".join(edited_paragraph.itertext()) == "English Français tail."
    assert etree.tostring(select_elements(document.tree(Part.CONTENT), "//style:style")[0]) == (
        etree.tostring(select_elements(after.tree(Part.CONTENT), "//style:style")[0])
    )
    repeated = tmp_path / ("repeated" + source.suffix)
    again = execute_operations(output, repeated, [operation])
    assert again.published
    assert not again.changed


def test_inline_language_keeps_other_channels_and_font_overrides(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    target, node = list(language_targets(document).items())[1]
    operation = SetTargetLanguages({
        target: TargetLanguage(asian="zh-Hant-TW", fingerprint=language_fingerprint(document, node))
    })
    output = tmp_path / "inline.fodt"
    result = execute_operations(source, output, [operation])
    assert result.published, result.as_dict()
    after = OdfDocument.open(output)
    inline = list(language_targets(after).values())[1]
    assert effective_languages(after, inline) == ("fr-FR", "zh-Hant-TW", "ar")
    styles = select_elements(after.tree(Part.CONTENT), "//style:style[@style:family='text']")
    assert len(styles) == 2
    for style in styles:
        props = style.find(qn("style", "text-properties"))
        assert props is not None
        assert props.get(qn("fo", "font-style")) == "italic"


def test_stale_fingerprint_refuses_every_target_before_mutation(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    (first, paragraph), (second, _) = language_targets(document).items()
    operation = SetTargetLanguages({
        first: TargetLanguage(western="de", fingerprint=language_fingerprint(document, paragraph)),
        second: TargetLanguage(western="de", fingerprint="0" * 16),
    })
    output = tmp_path / "refused.fodt"
    assert_refused(execute_operations(source, output, [operation]), match="fingerprint")
    assert not output.exists()


def test_audit_offers_target_decisions_without_guessing_language(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    report = audit_odf(source)
    questions = [question for question in report.decisions if question.kind.id == "language.target"]
    assert len(questions) == 2
    assert questions[1].current == {"western": "fr-FR", "asian": "ja", "complex": "ar"}


def test_table_language_edit_and_second_channel_preserve_grid_and_words(tmp_path: Path) -> None:
    body = (
        '<office:text><table:table table:name="Fruit"><table:table-column/>'
        '<table:table-row><table:table-cell office:value-type="string">'
        '<text:p text:style-name="Body">Apples</text:p></table:table-cell>'
        "</table:table-row></table:table></office:text>"
    )
    source = make_flat(tmp_path, "text", Variant(body=body, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    target, node = next(iter(language_targets(document).items()))
    fingerprint = language_fingerprint(document, node)
    first = tmp_path / "first.fodt"
    second = tmp_path / "second.fodt"
    assert execute_operations(
        source,
        first,
        [SetTargetLanguages({target: TargetLanguage(western="de", fingerprint=fingerprint)})],
    ).published
    result = execute_operations(
        first,
        second,
        [SetTargetLanguages({target: TargetLanguage(asian="zh-Hant", fingerprint=fingerprint)})],
    )
    assert result.published, result.as_dict()
    edited = OdfDocument.open(second)
    assert effective_languages(edited, next(iter(language_targets(edited).values()))) == (
        "de",
        "zh-Hant",
        "ar",
    )


def test_full_tag_inherited_from_paragraph_refuses_ineffective_inline_override(
    tmp_path: Path,
) -> None:
    styles = STYLES.replace(
        'fo:language="en" fo:country="GB"', 'style:rfc-language-tag="en-GB-x-fruit"'
    )
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=styles))
    document = OdfDocument.open(source)
    target, node = list(language_targets(document).items())[1]
    output = tmp_path / "refused.fodt"
    result = execute_operations(
        source,
        output,
        [
            SetTargetLanguages({
                target: TargetLanguage(
                    western="de", fingerprint=language_fingerprint(document, node)
                )
            })
        ],
    )
    assert_refused(result, match="Inherited full language tag")
    assert not output.exists()


@pytest.mark.parametrize("tag", ["en-u", "none-invalid-!", 42])
def test_invalid_language_is_refused_without_output(tmp_path: Path, tag: object) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    target, node = next(iter(language_targets(document).items()))
    output = tmp_path / "refused.fodt"
    result = execute_operations(
        source,
        output,
        [
            SetTargetLanguages({
                target: TargetLanguage(
                    western=cast("str", tag), fingerprint=language_fingerprint(document, node)
                )
            })
        ],
    )
    assert_refused(result, match="language tag")
    assert not output.exists()


def test_named_parent_and_automatic_direct_overrides_resolve_independently(tmp_path: Path) -> None:
    source = make_flat(
        tmp_path,
        "text",
        Variant(
            body='<office:text><text:p text:style-name="Direct">Bonjour</text:p></office:text>',
            automatic_styles=(
                '<style:style style:name="Direct" style:family="paragraph" '
                'style:parent-style-name="Named"><style:text-properties '
                'fo:language="fr" fo:country="CA"/></style:style>'
            ),
        ),
    )
    document = OdfDocument.open(source)
    root = document.tree(Part.STYLES).getroot()
    common = etree.Element(qn("office", "styles"))
    automatic = root.find(qn("office", "automatic-styles"))
    assert automatic is not None
    root.insert(root.index(automatic), common)
    style = etree.SubElement(common, qn("style", "style"))
    style.set(qn("style", "name"), "Named")
    style.set(qn("style", "family"), "paragraph")
    props = etree.SubElement(style, qn("style", "text-properties"))
    props.set(qn("fo", "language"), "en")
    props.set(qn("style", "language-asian"), "ja")
    props.set(qn("style", "language-complex"), "ar")
    assert effective_languages(document, next(iter(language_targets(document).values()))) == (
        "fr-CA",
        "ja",
        "ar",
    )


def test_unrelated_derived_style_change_is_detected_by_publication_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=STYLES))
    document = OdfDocument.open(source)
    target, node = next(iter(language_targets(document).items()))
    operation = SetTargetLanguages({
        target: TargetLanguage(western="de", fingerprint=language_fingerprint(document, node))
    })
    original = SetTargetLanguages.apply

    def corrupt_style(self: SetTargetLanguages, document: OdfDocument) -> tuple[Outcome, ...]:
        outcomes = original(self, document)
        styles = select_elements(document.tree(Part.CONTENT), "//style:style")
        props = styles[-1].find(qn("style", "text-properties"))
        assert props is not None
        props.set(qn("fo", "font-weight"), "normal")
        return outcomes

    monkeypatch.setattr(SetTargetLanguages, "apply", corrupt_style)
    output = tmp_path / "refused.fodt"
    assert_refused(execute_operations(source, output, [operation]), match="(?i)protected")
    assert not output.exists()


@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_language_source_controls(case: str) -> None:
    report = audit_odf(TESTS / "text_corpus" / f"language-{case}.odt")
    assert ("LANG004" in {f.rule_id for f in report.findings}) is (case == "negative")
    assert "LANG005" not in {f.rule_id for f in report.findings}


def test_unresolved_inheritance_is_reviewed_without_an_unsafe_question(tmp_path: Path) -> None:
    styles = STYLES.replace(
        'style:name="Body"', 'style:name="Body" style:parent-style-name="Missing"'
    )
    source = make_flat(tmp_path, "text", Variant(body=BODY, automatic_styles=styles))
    report = audit_odf(source)
    assert "LANG005" in {f.rule_id for f in report.findings}
    assert not any(question.kind.id == "language.target" for question in report.decisions)


@pytest.mark.parametrize("channel", ["asian", "complex"])
def test_nonwestern_declarations_are_not_misreported_as_absent(
    tmp_path: Path, channel: str
) -> None:
    language = "ja" if channel == "asian" else "ar"
    styles = (
        '<style:style style:name="Body" style:family="paragraph"><style:text-properties '
        f'style:language-{channel}="{language}"/></style:style>'
    )
    source = make_flat(
        tmp_path,
        "text",
        Variant(body=BODY.replace('text:style-name="French"', ""), automatic_styles=styles),
    )
    report = audit_odf(source)
    assert "LANG004" not in {finding.rule_id for finding in report.findings}
