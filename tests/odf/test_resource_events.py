# SPDX-License-Identifier: AGPL-3.0-only
"""Event navigation and declared database inputs have distinct resource contracts."""

lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.audit.engine import ExportContextMeasurements
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import OdfDocument, Part, qn, validate
from odfa11y.odf.export_context import native_export_limitations, require_native_context
from odfa11y.rules import registry as rules
from tests.fixtures.declarations import declaration
from tests.fixtures.measurements import measured, measurement


@pytest.mark.parametrize("action", ["show", "execute", "next-page", "sound"])
def test_presentation_events_classify_the_consumed_target_by_action(
    tmp_path: Path, action: str
) -> None:
    source = declaration(tmp_path, "image", None)
    document = OdfDocument.open(source)
    frame = document.tree(Part.CONTENT).find(".//" + qn("draw", "frame"))
    assert frame is not None
    listeners = etree.Element(qn("office", "event-listeners"))
    frame.insert(1, listeners)
    event = etree.SubElement(listeners, qn("presentation", "event-listener"))
    event.set(qn("script", "event-name"), "dom:click")
    event.set(qn("presentation", "action"), action)
    event.set(qn("xlink", "href"), "https://example.test/target")
    event.set(qn("xlink", "type"), "simple")
    if action == "sound":
        sound = etree.SubElement(event, qn("presentation", "sound"))
        sound.set(qn("xlink", "href"), "https://example.test/sound.wav")
        sound.set(qn("xlink", "type"), "simple")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    count = 1 if action in {"execute", "sound"} else 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == count
    if count:
        with pytest.raises(DocumentRefusal):
            require_native_context(reopened)
    else:
        require_native_context(reopened)


@pytest.mark.parametrize("binding", ["https://example.test/data.odb", "RegisteredDatabase", ""])
def test_form_input_binding_is_distinct_from_form_submission_navigation(
    tmp_path: Path, binding: str
) -> None:
    source = declaration(tmp_path, "form-image", "Pictures/asset.png")
    document = OdfDocument.open(source)
    document.storage.write_member("Pictures/asset.png", b"asset")
    form = document.tree(Part.CONTENT).find(".//" + qn("form", "form"))
    assert form is not None
    form.set(qn("form", "datasource"), binding)
    form.set(qn("xlink", "href"), "https://example.test/submit")
    form.set(qn("xlink", "type"), "simple")
    document.save(source)
    reopened = OdfDocument.open(source)
    assert validate(reopened).count == 0
    count = 1 if binding else 0
    assert native_export_limitations(reopened)["rendering_dependencies"] == count
    report = audit_odf(source)
    assert (
        measured(measurement(report, ExportContextMeasurements).limitations)[
            "rendering_dependencies"
        ]
        == count
    )
    assert (rules.NATIVE001.id in {f.rule_id for f in report.findings}) == bool(binding)
