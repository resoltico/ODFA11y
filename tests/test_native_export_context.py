# SPDX-License-Identifier: MPL-2.0
"""Known rendering dependencies are distinct from navigational links and document identity."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.content import native_export_limitations, require_native_context
from odfa11y.errors import ToolFailedError
from odfa11y.evidence import check_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .fixtures import make_minimal_odt
from .native_resource_fixtures import writer_resource

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "href",
    [
        "assets/nested/image.png",
        "file:///private/image.png",
        "https://example.test/image.png",
        "document.xml",
    ],
)
def test_flat_render_dependencies_are_reported_without_fetching(tmp_path: Path, href: str) -> None:
    source = writer_resource(tmp_path, href)
    report = audit_odf(source)
    assert "ODF012" in {finding.rule_id for finding in report.findings}
    assert report.metadata["native_export_limitations"]["rendering_dependencies"] == 1
    with pytest.raises(ToolFailedError, match="rendering dependencies"):
        require_native_context(OdfDocument.open(source))
    # Verify reaches the explicit native refusal even without any installed application.
    result = run_pipeline(
        source,
        [],
        FidelityPolicy(),
        tmp_path / "evidence",
        PipelineOptions(profile="verify", soffice="missing-tool"),
    )
    assert result.failed_stage == "export-source"
    assert result.exit_status == 3
    assert "rendering dependencies" in (result.stages[4].reason or "")
    assert check_bundle(tmp_path / "evidence") == []
    assert not (tmp_path / "evidence" / "source.pdf").exists()
    assert (tmp_path / "evidence" / "remediated.fodt").read_bytes() == source.read_bytes()


def test_embedded_bytes_and_navigation_are_supported_and_portable(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    assert native_export_limitations(document) == {
        "rendering_dependencies": 0,
        "location_fields": 0,
    }
    require_native_context(document, captured_identity=True)
    result = run_pipeline(
        source, [], FidelityPolicy(), tmp_path / "evidence", PipelineOptions(profile="inspect")
    )
    assert result.passed
    published = OdfDocument.open(tmp_path / "evidence" / "remediated.fodt")
    assert native_export_limitations(published)["rendering_dependencies"] == 0
    assert result.outputs == json.loads((tmp_path / "evidence" / "run.json").read_text())["outputs"]


def test_filename_fields_stay_authored_in_source_only_workflow(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    root = document.edit(Part.CONTENT).getroot()
    paragraph = root.find(".//" + qn("text", "p"))
    assert paragraph is not None

    field = etree.SubElement(paragraph, qn("text", "file-name"))
    field.set(qn("text", "display"), "full")
    field.text = "Authored cached field"
    document.save(source)
    assert "ODF013" in {finding.rule_id for finding in audit_odf(source).findings}
    require_native_context(OdfDocument.open(source))  # Direct original export is distinct.
    with pytest.raises(ToolFailedError, match="filename/path fields"):
        require_native_context(OdfDocument.open(source), captured_identity=True)
    output = tmp_path / "evidence"
    result = run_pipeline(source, [], FidelityPolicy(), output, PipelineOptions(profile="inspect"))
    assert result.passed
    assert (output / "remediated.fodt").read_bytes() == source.read_bytes()


def test_explicit_base_on_render_reference_is_unestablished(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "image.odt", features={"with_image_without_alt": True})
    document = OdfDocument.open(source)
    image = document.edit(Part.CONTENT).find(".//" + qn("draw", "image"))
    assert image is not None
    image.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/assets/")
    document.save(source)
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 1


def test_navigation_xml_base_is_not_a_render_dependency(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    link = document.edit(Part.CONTENT).find(".//" + qn("text", "a"))
    assert link is not None
    link.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/docs/")
    document.save(source)
    require_native_context(OdfDocument.open(source), captured_identity=True)
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 0
