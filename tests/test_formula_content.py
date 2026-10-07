# SPDX-License-Identifier: MPL-2.0
"""Semantic expression presence is stronger than valid nonempty MathML structure."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.odf import OdfDocument, Part, qn, validate

SOURCE = Path(__file__).parent / "family_corpus/sum-formula.odf"


def _expression(tmp_path: Path, xml: str) -> Path:
    document = OdfDocument.open(SOURCE)
    root = document.edit(Part.CONTENT).getroot()
    root[:] = []
    root.set("alttext", "An explicitly reviewed alternative")
    root.append(
        etree.fromstring(f'<math xmlns="http://www.w3.org/1998/Math/MathML">{xml}</math>'.encode())[
            0
        ]
    )
    assert validate(document).count == 0
    return document.save(tmp_path / "expression.odf")


@pytest.mark.parametrize(
    "xml",
    [
        "<mi/>",
        "<mi> </mi>",
        "<mfrac><mrow/><mrow/></mfrac>",
        "<mspace/>",
        '<ms lquote="" rquote=""/>',
        "<mphantom><mi>x</mi></mphantom>",
        '<semantics><mrow/><annotation encoding="StarMath 5.0">a+b</annotation></semantics>',
    ],
)
def test_schema_valid_empty_or_invisible_expressions_fail_semantic_audit(
    tmp_path: Path, xml: str
) -> None:
    report = audit_odf(_expression(tmp_path, xml), schema=True)
    assert "MATH001" in {finding.rule_id for finding in report.findings}
    assert "MATH002" not in {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize(
    "value",
    [
        "pi",
        "exponentiale",
        "imaginaryi",
        "infinity",
        "integers",
        "reals",
        "emptyset",
        "true",
        "false",
        "set",
        "list",
        "vector",
        "matrix",
    ],
)
def test_mathml_content_values_are_meaningful_without_token_text(
    tmp_path: Path, value: str
) -> None:
    report = audit_odf(_expression(tmp_path, f"<{value}/>"), schema=True)
    assert "MATH001" not in {finding.rule_id for finding in report.findings}


@pytest.mark.parametrize(
    "xml",
    [
        "<mi>x</mi>",
        "<mn>0</mn>",
        "<mo>+</mo>",
        "<ms/>",
        '<csymbol definitionURL="https://example.invalid/meaning"/>',
        "<apply><plus/><ci>x</ci><cn>1</cn></apply>",
    ],
)
def test_presentation_and_content_tokens_are_meaningful(tmp_path: Path, xml: str) -> None:
    report = audit_odf(_expression(tmp_path, xml), schema=True)
    assert "MATH001" not in {finding.rule_id for finding in report.findings}


def test_remote_glyph_remains_a_resource_warning_without_fetching(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    root = document.edit(Part.CONTENT).getroot()
    root[:] = []
    root.set("alttext", "A mathematical glyph")
    token = etree.SubElement(root, qn("math", "mi"))
    etree.SubElement(
        token, qn("math", "mglyph"), src="https://invalid.example/glyph.svg", alt="symbol"
    )
    assert validate(document).count == 0
    report = audit_odf(document.save(tmp_path / "glyph.odf"), schema=True)
    ids = {finding.rule_id for finding in report.findings}
    assert "MATH001" not in ids
    assert "MATH003" in ids
