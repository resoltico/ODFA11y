# SPDX-License-Identifier: MPL-2.0
"""Writer-produced revision fixture retains word boundaries and excluded contexts."""

import re
lazy from collections.abc import Callable
lazy from pathlib import Path

from lxml import etree
from pypdf import PdfReader

from odfa11y.application.export import export_document
from odfa11y.application.tools import Tools
from odfa11y.audit import audit_odf
from odfa11y.families.text.headings.audit import TextContentMeasurements
from odfa11y.odf import OdfDocument, Part, select_elements, validate
from tests.fixtures.answers import metadata_input
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.operations import apply_answers
from tests.fixtures.paths import TESTS

FIXTURE = TESTS / "corpus/reproductions/text-contexts.odt"


def test_writer_revision_reload_and_rendered_word_boundaries(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    before = OdfDocument.open(FIXTURE)
    assert measured(measurement(audit_odf(FIXTURE), TextContentMeasurements).heading_count) == 1
    edited = tmp_path / "reviewed.odt"
    apply_answers(FIXTURE, edited, [metadata_input(title="Reviewed context fixture")])
    after = OdfDocument.open(edited)
    assert validate(after).count == validate(before).count
    for expression in (
        "//text:tracked-changes",
        "//text:note",
        "//office:annotation",
        "//text:section",
    ):
        left = select_elements(before.tree(Part.CONTENT), expression)
        right = select_elements(after.tree(Part.CONTENT), expression)
        assert left
        assert len(left) == len(right)
        assert [etree.tostring(node) for node in left] == [etree.tostring(node) for node in right]
    output = tmp_path / "rendered.pdf"
    export_document(edited, output, Tools(soffice=soffice))
    text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
    assert re.search(r"One\s+Two\s+Three\s+Four", text)
    assert "Deleted heading" not in text
    assert "Note heading" in text
