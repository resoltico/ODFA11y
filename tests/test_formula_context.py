# SPDX-License-Identifier: MPL-2.0
"""Independent declaration controls for formula-aware native preflight."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.content import native_export_limitations, require_native_context
from odfa11y.content.formula_context import FORMULA_ATTRIBUTES
from odfa11y.content.formula_syntax import (
    CELL_QUERIES,
    INFO_QUERIES,
    MAX_CHARACTERS,
    OPENFORMULA,
    FormulaFacts,
    classify_formula,
)
from odfa11y.errors import ToolFailedError
from odfa11y.odf import OdfDocument, Part, qn
from odfa11y.pipeline import export_document
from odfa11y.report import FactKeys

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def classify(expression: str, prefix: str = "of") -> FormulaFacts:
    return classify_formula(expression, {prefix: OPENFORMULA}, lambda _: FormulaFacts(incomplete=1))


@pytest.mark.parametrize(
    "expression",
    [
        "of:=SUM([.A1:.A3])",
        'of:=IF([Sheet1.A1]>0;SUM([.A1];2);"DDE(never a call)")',
        'of:=HYPERLINK("https://example.test/";"Navigation")',
        "of:=SUM([$Sheet1.$A$1];['Two sheets'.B2])",
        "of:=1.2E-3+(2*3)^2%",
        "of:=IFERROR(#DIV/0!;FALSE())",
        "=SUM([.A1:.A3])",
        "SUM([.A1:.A3])",
        'of:="escaped ""DDE"" text"',
    ],
)
def test_supported_local_grammar_never_scans_string_literals(expression: str) -> None:
    assert classify(expression) == FormulaFacts()
    assert classify(expression.replace("of:", "formula:"), "formula") == FormulaFacts()


@pytest.mark.parametrize(
    "expression",
    [
        'of:=DDE("service";"source";"item")',
        'of:=IF(FALSE();DDE("service";"source";"item");1)',
        "of:=['https://example.test/book'#Sheet1.A1]",
    ],
)
def test_explicit_loading_is_detected_even_in_unreachable_branches(expression: str) -> None:
    assert classify(expression).loading == 1


@pytest.mark.parametrize(
    "expression",
    [
        'of:=INDIRECT("A1")',
        "of:=CELL([.A1])",
        'of:=INFO("vendor category")',
        "of:=VENDORFUNCTION(1)",
        "vendor:=SUM([.A1])",
        "of:=SUM([.A1]",
        "of:=1 2",
        "of:=#VENDOR!",
        "of:=cell-content()>1",
        pytest.param("of:=" + "(" * 100 + "1" + ")" * 100, id="nesting-depth-budget"),
        pytest.param("of:=" + "-" * 100 + "1", id="unary-depth-budget"),
        pytest.param("of:=" + "1+" * 3000 + "1", id="token-budget"),
        pytest.param('of:="' + "x" * MAX_CHARACTERS + '"', id="character-budget"),
    ],
)
def test_unestablished_syntax_or_dynamic_context_cannot_pass_clean(expression: str) -> None:
    assert classify(expression).incomplete == 1


@pytest.mark.parametrize("query", sorted(CELL_QUERIES))
def test_normative_cell_queries_are_classified(query: str) -> None:
    assert classify(f'of:=CELL("{query}";[.A1])') == FormulaFacts(identity=int(query == "FILENAME"))


@pytest.mark.parametrize("query", sorted(INFO_QUERIES))
def test_normative_info_queries_are_classified(query: str) -> None:
    assert classify(f'of:=INFO("{query.lower()}")') == FormulaFacts(
        identity=int(query == "DIRECTORY")
    )


def formula_document(tmp_path: Path, expression: str, attribute: str) -> Path:
    source = make_minimal_odt(tmp_path / "formula.odt")
    document = OdfDocument.open(source)
    root = document.tree(Part.CONTENT).getroot()
    body = root.find(".//" + qn("office", "text"))
    assert body is not None
    node = etree.SubElement(
        body,
        qn("text", "variable-set"),
        nsmap={"of": OPENFORMULA},
    )
    node.set(attribute, expression)
    node.text = "Private cached result"
    document.save(source)
    return source


@pytest.mark.parametrize("attribute", sorted(FORMULA_ATTRIBUTES))
def test_every_standard_formula_attribute_reaches_the_native_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    source = formula_document(
        tmp_path, 'of:=DDE("private service";"credentials";"item")', attribute
    )
    original = source.read_bytes()
    calls = []
    monkeypatch.setattr("odfa11y.pipeline.native.export_pdfua", lambda *args: calls.append(args))
    with pytest.raises(ToolFailedError, match="formula context"):
        export_document(source, tmp_path / "destination.pdf")
    assert calls == []
    assert not (tmp_path / "destination.pdf").exists()
    report = audit_odf(source)
    assert "ODF012" in {f.rule_id for f in report.findings}
    assert "credentials" not in str(report.facts)
    assert report.facts[FactKeys.NATIVE_LIMITATIONS]["formula_declarations"] == 1
    assert source.read_bytes() == original


def test_captured_identity_and_original_export_are_separate(tmp_path: Path) -> None:
    source = formula_document(tmp_path, 'of:=CELL("FILENAME")', qn("text", "formula"))
    document = OdfDocument.open(source)
    require_native_context(document)
    with pytest.raises(ToolFailedError, match="filename/path fields"):
        require_native_context(document, captured_identity=True)
    assert "ODF013" in {f.rule_id for f in audit_odf(source).findings}


@pytest.mark.parametrize("expression", ["of:=LocalTotal", "of:=Missing", "of:=Cycle"])
def test_named_dependencies_follow_declarations_and_refuse_missing_or_cycles(
    tmp_path: Path, expression: str
) -> None:
    source = formula_document(tmp_path, expression, qn("table", "formula"))
    document = OdfDocument.open(source)
    root = document.tree(Part.CONTENT).getroot()
    names = etree.SubElement(root, qn("table", "named-expressions"))
    for name, formula in [("LocalTotal", "of:=SUM([.A1:.A3])"), ("Cycle", "of:=Cycle")]:
        declaration = etree.SubElement(
            names, qn("table", "named-expression"), nsmap={"of": OPENFORMULA}
        )
        declaration.set(qn("table", "name"), name)
        declaration.set(qn("table", "expression"), formula)
    # Unused cyclic declarations are still inspected rather than hidden by reachability.
    assert native_export_limitations(document)["formula_incomplete"] >= 1
    names.remove(names[-1])
    limits = native_export_limitations(document)
    assert limits["formula_incomplete"] == int(expression != "of:=LocalTotal")


def test_embedded_odf_styles_and_nested_formula_contexts_are_inspected(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "embedded.odt")
    document = OdfDocument.open(source)
    body = document.tree(Part.CONTENT).find(".//" + qn("office", "text"))
    assert body is not None
    frame = etree.SubElement(body, qn("draw", "frame"))
    obj = etree.SubElement(frame, qn("draw", "object"))
    obj.set(qn("xlink", "href"), "./Object1")
    document.storage.write_member(
        "Object1/content.xml",
        b"<office:document-content "
        b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
        b"<office:body/></office:document-content>",
    )
    document.storage.write_member(
        "Object1/styles.xml",
        b"<office:document-styles "
        b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        b'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        b'xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2">'
        b'<style:map style:condition="of:=INDIRECT(&quot;A1&quot;)"/>'
        b"</office:document-styles>",
    )
    limits = native_export_limitations(document)
    assert limits["formula_declarations"] == limits["formula_origins"] == 1
    assert limits["formula_incomplete"] == 1
    with pytest.raises(ToolFailedError, match="formula context"):
        require_native_context(document)


@pytest.mark.parametrize("duplicate", [False, True])
def test_scoped_names_shadow_globals_and_case_collisions_refuse(
    tmp_path: Path, *, duplicate: bool
) -> None:
    source = make_minimal_odt(tmp_path / "scopes.odt")
    document = OdfDocument.open(source)
    root = document.tree(Part.CONTENT).getroot()
    body = root.find(".//" + qn("office", "text"))
    assert body is not None
    table = etree.SubElement(body, qn("table", "table"))
    declarations = etree.SubElement(table, qn("table", "named-expressions"))
    for name in ["Total", "TOTAL"] if duplicate else ["Total"]:
        node = etree.SubElement(
            declarations, qn("table", "named-expression"), nsmap={"of": OPENFORMULA}
        )
        node.set(qn("table", "name"), name)
        node.set(qn("table", "expression"), "of:=SUM([.A1:.A3])")
    cell = etree.SubElement(table, qn("table", "table-cell"), nsmap={"of": OPENFORMULA})
    cell.set(qn("table", "formula"), "of:=total")
    limits = native_export_limitations(document)
    assert limits["formula_incomplete"] == int(duplicate)


@pytest.mark.parametrize(
    "attribute",
    [
        qn("style", "base-cell-address"),
        qn("table", "base-cell-address"),
        qn("table", "cell-range-address"),
    ],
)
def test_source_or_base_range_addresses_cannot_hide_external_loading(
    tmp_path: Path, attribute: str
) -> None:
    source = formula_document(tmp_path, "'https://example.test/source'#Sheet1.A1", attribute)
    limits = native_export_limitations(OdfDocument.open(source))
    assert limits["rendering_dependencies"] == 1
    assert limits["formula_declarations"] == 1


def test_malformed_reachable_embedded_xml_is_explicitly_incomplete(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "embedded-malformed.odt")
    document = OdfDocument.open(source)
    body = document.tree(Part.CONTENT).find(".//" + qn("office", "text"))
    assert body is not None
    obj = etree.SubElement(body, qn("draw", "object"))
    obj.set(qn("xlink", "href"), "./Object1")
    document.storage.write_member("Object1/content.xml", b"malformed embedded XML")
    limits = native_export_limitations(document)
    assert limits["formula_incomplete"] == 1
    with pytest.raises(ToolFailedError, match="formula context"):
        require_native_context(document)
