# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for page family exports."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.concepts import GraphicAlternative, PageDecision
from odfa11y.evidence import check_bundle
from odfa11y.families import pages
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.remediate import SetMetadata
from odfa11y.report import FactKeys
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.families.pages.test_page_family_exports import CORPUS, FAMILIES, _plan
from tests.fixtures.plans import reviewed_plan


@pytest.mark.parametrize("family", FAMILIES)
def test_native_page_pipeline_has_independent_positive_and_negative_pdf_controls(
    tmp_path: Path, family: str, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    suffix, _ = FAMILIES[family]
    source = CORPUS / f"fruit-{family}{suffix}"
    root = tmp_path / "evidence"
    record = execute(
        source,
        reviewed_plan(source, _plan(family), FidelityPolicy()),
        root,
        RunSettings(
            tools=Tools(soffice=soffice, verapdf=verapdf), profile=profile_named("production")
        ),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    assert all(stage.status == "passed" for stage in record.stages)
    assert check_bundle(root) == []
    assert "PDF007" in {f.rule_id for f in audit_pdfua(root / "source.pdf").findings}
    damaged = validate_pdfua(root / "source.pdf", executable=verapdf)
    assert not damaged.compliant
    assert {(failure.clause, failure.test_number) for failure in damaged.failures} == {("7.3", "1")}
    assert validate_pdfua(root / "remediated.pdf", executable=verapdf).compliant
    assert audit_pdfua(root / "remediated.pdf").facts[FactKeys.PDF_STRUCTURE_TAGS]["Figure"] == 1


def test_described_illustration_only_draw_export_passes_both_content_checks(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    doc = OdfDocument.open(CORPUS / "fruit-drawing.odg")
    page = select_elements(doc.tree(Part.CONTENT), "//office:body/office:drawing/draw:page")[0]
    for shape in list(page):
        if shape.get(qn("draw", "name")) != "Fruit illustration":
            page.remove(shape)
    page.set(qn("draw", "nav-order"), "id3")
    source = doc.save(tmp_path / "illustration.odg")
    root = tmp_path / "evidence"
    plan = [
        SetMetadata(language="en-US"),
        pages.SetPageSemantics({"Fruit overview": PageDecision("Fruit illustration")}),
        pages.SetGraphicAlternatives({
            "Fruit illustration": GraphicAlternative(
                "Fruit illustration", "A red apple and a green pear"
            )
        }),
    ]
    record = execute(
        source,
        reviewed_plan(source, plan, FidelityPolicy()),
        root,
        RunSettings(
            tools=Tools(soffice=soffice, verapdf=verapdf), profile=profile_named("production")
        ),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    report = audit_pdfua(root / "remediated.pdf")
    assert report.facts[FactKeys.PDF_TEXT_CHARACTER_COUNT] == 0
    assert report.facts[FactKeys.PDF_DESCRIBED_GRAPHIC_COUNT] == 1
    assert "PDF010" not in {finding.rule_id for finding in report.findings}
    assert validate_pdfua(root / "remediated.pdf", executable=verapdf).compliant
