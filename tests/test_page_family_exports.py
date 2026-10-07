# SPDX-License-Identifier: MPL-2.0
"""Real current Impress/Draw documents prove source repair and complete PDF assurance."""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf
from odfa11y.content import GraphicDescription, PageDecision
from odfa11y.evidence import check_bundle
from odfa11y.families import drawing, presentation
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.adapter import Operation

CORPUS = Path(__file__).parent / "family_corpus"
FAMILIES = {"presentation": (".odp", presentation), "drawing": (".odg", drawing)}


def _plan(family: str) -> list[Operation]:
    _, api = FAMILIES[family]
    return [
        SetMetadata(language="en-US"),
        api.SetPageSemantics({
            "Fruit overview": PageDecision(
                "Fruit overview", "Fruit counts and an illustration", ("id2", "id1", "id3")
            )
        }),
        api.SetGraphicDescriptions({
            "Fruit illustration": GraphicDescription(
                "Fruit illustration", "A red apple and a green pear"
            )
        }),
    ]


def test_native_family_corpus_matches_provenance_and_validates() -> None:
    manifest = tomllib.loads((CORPUS / "manifest.toml").read_text())
    assert manifest["producer"] == "LibreOffice 26.8.0.3"
    expected = {f"fruit-{family}{suffix}" for family, (suffix, _) in FAMILIES.items()}
    assert {entry["file"] for entry in manifest["documents"]} == expected
    for entry in manifest["documents"]:
        source = CORPUS / entry["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
        result = validate(OdfDocument.open(source))
        assert result.version == manifest["odf_version"] == "1.4"
        assert result.count == entry["schema_violations"] == 0


@pytest.mark.parametrize("family", FAMILIES)
def test_native_page_plan_removes_its_findings_and_reapplies_unchanged(
    tmp_path: Path, family: str
) -> None:
    suffix, _ = FAMILIES[family]
    source = CORPUS / f"fruit-{family}{suffix}"
    once, twice = tmp_path / f"once{suffix}", tmp_path / f"twice{suffix}"
    assert remediate(source, once, _plan(family)).changed
    assert not remediate(once, twice, _plan(family)).changed
    assert audit_odf(twice, schema=True).findings == []
    assert once.read_bytes() == twice.read_bytes()


@pytest.mark.integration
@pytest.mark.parametrize("family", FAMILIES)
def test_native_page_pipeline_has_independent_positive_and_negative_pdf_controls(
    tmp_path: Path, family: str, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    suffix, _ = FAMILIES[family]
    source = CORPUS / f"fruit-{family}{suffix}"
    root = tmp_path / "evidence"
    record = run_pipeline(
        source,
        _plan(family),
        FidelityPolicy(),
        root,
        PipelineOptions(profile="production", soffice=soffice, verapdf_path=verapdf),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    assert all(stage.status == "passed" for stage in record.stages)
    assert check_bundle(root) == []
    assert "PDF007" in {f.rule_id for f in audit_pdfua(root / "source.pdf").findings}
    damaged = validate_pdfua(root / "source.pdf", executable=verapdf)
    assert not damaged.compliant
    assert {(failure.clause, failure.test_number) for failure in damaged.failures} == {("7.3", "1")}
    assert validate_pdfua(root / "remediated.pdf", executable=verapdf).compliant
    assert audit_pdfua(root / "remediated.pdf").metadata["structure_tags"]["Figure"] == 1


@pytest.mark.integration
def test_described_illustration_only_draw_export_passes_both_content_checks(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    doc = OdfDocument.open(CORPUS / "fruit-drawing.odg")
    page = select_elements(doc.edit(Part.CONTENT), "//office:body/office:drawing/draw:page")[0]
    for shape in list(page):
        if shape.get(qn("draw", "name")) != "Fruit illustration":
            page.remove(shape)
    page.set(qn("draw", "nav-order"), "id3")
    source = doc.save(tmp_path / "illustration.odg")
    root = tmp_path / "evidence"
    plan = [
        SetMetadata(language="en-US"),
        drawing.SetPageSemantics({"Fruit overview": PageDecision("Fruit illustration")}),
        drawing.SetGraphicDescriptions({
            "Fruit illustration": GraphicDescription(
                "Fruit illustration", "A red apple and a green pear"
            )
        }),
    ]
    record = run_pipeline(
        source,
        plan,
        FidelityPolicy(),
        root,
        PipelineOptions(profile="production", soffice=soffice, verapdf_path=verapdf),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    report = audit_pdfua(root / "remediated.pdf")
    assert report.metadata["extractable_text_characters"] == 0
    assert report.metadata["described_graphics"] == 1
    assert "PDF010" not in {finding.rule_id for finding in report.findings}
    assert validate_pdfua(root / "remediated.pdf", executable=verapdf).compliant
