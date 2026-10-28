# SPDX-License-Identifier: MPL-2.0
"""Paragraph style scopes establish safe break and spacing decisions before mutations."""

from __future__ import annotations

import zipfile
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.families.text import NormalizeSpacing, RemoveEmptySpacers
from odfa11y.families.text.styles import catalog_of
from odfa11y.odf import NS, OdfDocument, Part, qn, select_elements, validate
from odfa11y.outcomes import StageStatus
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf

from .documents import Variant, make_package
from .fixtures import make_minimal_odt
from .operation_execution import assert_refused, execute_operations

if TYPE_CHECKING:
    from pathlib import Path


def _style(document: OdfDocument, name: str, *, automatic: bool = False) -> etree._Element:
    tree = document.tree(Part.CONTENT if automatic else Part.STYLES)
    container = tree.find("office:automatic-styles" if automatic else "office:styles", NS)
    assert container is not None
    return etree.SubElement(
        container,
        qn("style", "style"),
        {qn("style", "name"): name, qn("style", "family"): "paragraph"},
    )


def _empty(document: OdfDocument, style: str) -> etree._Element:
    body = document.tree(Part.CONTENT).find("office:body/office:text", NS)
    assert body is not None
    return etree.SubElement(body, qn("text", "p"), {qn("text", "style-name"): style})


def test_foreign_style_cannot_shadow_a_real_page_break(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    authored = document.tree(Part.STYLES).find("office:styles/style:style[@style:name='Body']", NS)
    assert authored is not None
    props = authored.find("style:paragraph-properties", NS)
    assert props is not None
    props.set(qn("fo", "break-before"), "page")
    paragraph = _empty(document, "Body")
    body = paragraph.getparent()
    assert body is not None
    foreign = etree.SubElement(body, "{urn:example:foreign}payload")
    container = etree.SubElement(foreign, qn("office", "styles"))
    shadow = deepcopy(authored)
    shadow_props = shadow.find("style:paragraph-properties", NS)
    assert shadow_props is not None
    shadow_props.set(qn("fo", "break-before"), "auto")
    container.append(shadow)
    before = etree.tostring(foreign)
    assert RemoveEmptySpacers().apply(document)[0].status is Status.UNCHANGED
    assert paragraph.getparent() is body
    assert etree.tostring(foreign) == before
    source = document.save(tmp_path / "source.odt")
    result = execute_operations(source, tmp_path / "out.odt", [RemoveEmptySpacers()])
    assert not result.changed
    assert select_elements(
        OdfDocument.open(tmp_path / "out.odt").tree(Part.CONTENT),
        "//office:text/text:p[@text:style-name='Body' and not(text())]",
    )


def test_automatic_parent_uses_common_scope_even_when_names_match(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    common = _style(document, "Shared")
    etree.SubElement(common, qn("style", "paragraph-properties")).set(
        qn("fo", "break-before"), "page"
    )
    automatic = _style(document, "Shared", automatic=True)
    automatic.set(qn("style", "parent-style-name"), "Shared")
    etree.SubElement(automatic, qn("style", "paragraph-properties")).set(
        qn("fo", "margin-top"), "1cm"
    )
    paragraph = _empty(document, "Shared")
    properties = catalog_of(document).effective_paragraph_properties("Shared")
    assert properties[qn("fo", "break-before")] == "page"
    assert properties[qn("fo", "margin-top")] == "1cm"
    assert RemoveEmptySpacers().apply(document)[0].status is not Status.FAILED
    assert paragraph.getparent() is not None
    assert len(catalog_of(document).styles("paragraph")) == 5


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "parent",
        "automatic-parent",
        "cycle",
        "duplicate",
        "automatic-duplicate",
        "map",
        "properties",
        "default",
        "containers",
    ],
)
def test_unresolved_spacer_styles_fail_before_removing_any_candidate(
    tmp_path: Path, problem: str
) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    _empty(document, "BodyTight")  # an earlier removable paragraph must remain on failure
    unknown = _empty(document, "Unresolved")
    _unresolved_style(document, problem)
    before = etree.tostring(document.tree(Part.CONTENT))
    outcome = RemoveEmptySpacers().apply(document)[0]
    assert outcome.status is Status.FAILED
    assert unknown.getparent() is not None
    assert etree.tostring(document.tree(Part.CONTENT)) == before
    source = document.save(tmp_path / "source.odt")
    destination = tmp_path / "out.odt"
    assert_refused(execute_operations(source, destination, [RemoveEmptySpacers()]))
    assert not destination.exists()
    report = audit_odf(source)
    assert "STYLE001" in {finding.rule_id for finding in report.findings}
    assert report.facts[FactKeys.TEXT_HEADING_COUNT] == 1
    if problem not in {"default", "containers"}:
        assert any(row["style"] == "Body" for row in report.facts[FactKeys.TEXT_PARAGRAPH_STYLES])


def test_spacing_refuses_conditional_target_before_creating_a_style(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    target = document.tree(Part.STYLES).find(
        "office:styles/style:style[@style:name='BodyTight']", NS
    )
    assert target is not None
    etree.SubElement(target, qn("style", "map"))
    paragraph = _empty(document, "BodyTight")
    paragraph.text = "Target paragraph"
    before = etree.tostring(document.tree(Part.CONTENT))
    outcome = NormalizeSpacing("Body paragraph.", ("BodyTight",)).apply(document)[0]
    assert outcome.status is Status.FAILED
    assert etree.tostring(document.tree(Part.CONTENT)) == before


def _unresolved_style(document: OdfDocument, problem: str) -> None:
    if problem == "missing":
        return
    style = _style(document, "Unresolved")
    if problem in {"parent", "automatic-parent"}:
        style.set(qn("style", "parent-style-name"), "Missing")
        if problem == "automatic-parent":
            _style(document, "Missing", automatic=True)
    elif problem == "cycle":
        style.set(qn("style", "parent-style-name"), "Unresolved")
    elif problem == "map":
        etree.SubElement(style, qn("style", "map"))
    else:
        _ambiguous_style(document, style, problem)


def _ambiguous_style(document: OdfDocument, style: etree._Element, problem: str) -> None:
    if problem == "duplicate":
        _style(document, "Unresolved")
    elif problem == "automatic-duplicate":
        for _ in range(2):
            _style(document, "Unresolved", automatic=True)
    elif problem == "properties":
        for _ in range(2):
            etree.SubElement(style, qn("style", "paragraph-properties"))
    elif problem == "containers":
        etree.SubElement(document.tree(Part.STYLES).getroot(), qn("office", "styles"))
    elif problem == "default":
        container = document.tree(Part.STYLES).find("office:styles", NS)
        assert container is not None
        etree.SubElement(
            container, qn("style", "default-style"), {qn("style", "family"): "paragraph"}
        )


@pytest.mark.parametrize("scope", ["default", "common", "automatic"])
@pytest.mark.parametrize("number", ["0", "1"])
def test_inherited_page_number_reset_protects_empty_paragraphs(
    tmp_path: Path, scope: str, number: str
) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "original.odt"))
    if scope == "default":
        style = document.tree(Part.STYLES).find("office:styles/style:default-style", NS)
        assert style is not None
    else:
        style = _style(document, "PageControl", automatic=scope == "automatic")
    props = etree.Element(qn("style", "paragraph-properties"))
    style.insert(0, props)
    props.set(qn("style", "page-number"), number)
    inherited = (
        style if scope == "automatic" else _style(document, "PageControlUse", automatic=True)
    )
    if scope == "common":
        inherited.set(qn("style", "parent-style-name"), "PageControl")
    name = inherited.get(qn("style", "name"), "")
    paragraph = _empty(document, name)
    assert validate(document).count == 0
    source = document.save(tmp_path / "source.odt")
    result = execute_operations(source, tmp_path / "out.odt", [RemoveEmptySpacers()])
    reloaded = OdfDocument.open(tmp_path / "out.odt")
    targets = select_elements(
        reloaded.tree(Part.CONTENT), f"//office:text/text:p[@text:style-name='{name}']"
    )
    assert len(targets) == 1
    assert paragraph.get(qn("text", "style-name")) == name
    part = Part.STYLES if scope != "automatic" else Part.CONTENT
    declarations = select_elements(
        reloaded.tree(part), f"//style:paragraph-properties[@style:page-number='{number}']"
    )
    assert len(declarations) == 1
    assert result.schema.status == StageStatus.PASSED
    assert result.schema.new_count == 0


@pytest.mark.parametrize("missing", [False, True])
def test_optional_styles_absence_is_distinct_from_an_unrecognized_styles_root(
    tmp_path: Path, *, missing: bool
) -> None:
    original = make_package(
        tmp_path,
        "text",
        Variant(body=("<office:text><text:p/><text:p>Meaningful text</text:p></office:text>")),
    )
    source = tmp_path / "source.odt"
    if missing:
        with zipfile.ZipFile(original) as full, zipfile.ZipFile(source, "w") as cut:
            for member in full.infolist():
                if member.filename != "styles.xml":
                    cut.writestr(member, full.read(member.filename))
    else:
        document = OdfDocument.open(original)
        document.tree(Part.STYLES).getroot().tag = qn("office", "document-content")
        document.save(source)
    output = tmp_path / "out.odt"
    if missing:
        result = execute_operations(source, output, [RemoveEmptySpacers()])
        assert result.changed
        assert not OdfDocument.open(output).has(Part.STYLES)
    else:
        assert_refused(
            execute_operations(source, output, [RemoveEmptySpacers()]), match="unsupported root"
        )
        assert not output.exists()
        assert "STYLE001" in {finding.rule_id for finding in audit_odf(source).findings}
