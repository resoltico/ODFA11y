# SPDX-License-Identifier: MPL-2.0
"""Known rendering dependencies are distinct from navigational links and document identity."""

import json
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.application.tools import Tools
from odfa11y.audit import audit_odf
from odfa11y.audit.engine import ExportContextMeasurements
from odfa11y.errors import DocumentRefusal
from odfa11y.evidence import check_bundle
from odfa11y.odf import OdfDocument, Part, qn
from odfa11y.odf.export_context import native_export_limitations, require_native_context
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native_resources import writer_resource
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt


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
    assert rules.NATIVE001.id in {finding.rule_id for finding in report.findings}
    assert (
        measured(measurement(report, ExportContextMeasurements).limitations)[
            "rendering_dependencies"
        ]
        == 1
    )
    with pytest.raises(DocumentRefusal, match="resource"):
        require_native_context(OdfDocument.open(source))
    # Verify reaches the explicit native refusal even without any installed application.
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        tmp_path / "evidence",
        RunSettings(tools=Tools(soffice="missing-tool"), profile=profile_named("verify")),
    )
    assert result.failed_stage == "export-source"
    assert result.exit_status == 2
    assert "frame 'Asset'" in (result.stages[4].reason or "")
    assert "resource" in (result.stages[4].reason or "")
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
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        tmp_path / "evidence",
        RunSettings(profile=profile_named("source")),
    )
    assert result.passed
    published = OdfDocument.open(tmp_path / "evidence" / "remediated.fodt")
    assert native_export_limitations(published)["rendering_dependencies"] == 0
    assert result.outputs == json.loads((tmp_path / "evidence" / "run.json").read_text())["outputs"]


def test_filename_fields_stay_authored_in_source_only_workflow(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    root = document.tree(Part.CONTENT).getroot()
    paragraph = root.find(".//" + qn("text", "p"))
    assert paragraph is not None

    field = etree.SubElement(paragraph, qn("text", "file-name"))
    field.set(qn("text", "display"), "full")
    field.text = "Authored cached field"
    document.save(source)
    assert rules.NATIVE002.id in {finding.rule_id for finding in audit_odf(source).findings}
    require_native_context(OdfDocument.open(source))  # Direct original export is distinct.
    with pytest.raises(DocumentRefusal, match="filename/path fields"):
        require_native_context(OdfDocument.open(source), captured_identity=True)
    output = tmp_path / "evidence"
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        output,
        RunSettings(profile=profile_named("source")),
    )
    assert result.passed
    assert (output / "remediated.fodt").read_bytes() == source.read_bytes()


def test_explicit_base_on_render_reference_is_unestablished(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "image.odt", features={"with_image_without_alt": True})
    document = OdfDocument.open(source)
    image = document.tree(Part.CONTENT).find(".//" + qn("draw", "image"))
    assert image is not None
    image.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/assets/")
    document.save(source)
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 1


def test_navigation_xml_base_is_not_a_render_dependency(tmp_path: Path) -> None:
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    link = document.tree(Part.CONTENT).find(".//" + qn("text", "a"))
    assert link is not None
    link.set("{http://www.w3.org/XML/1998/namespace}base", "https://example.test/docs/")
    document.save(source)
    require_native_context(OdfDocument.open(source), captured_identity=True)
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 0
