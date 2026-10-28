# SPDX-License-Identifier: MPL-2.0
"""Writer-produced revision fixture retains word boundaries and excluded contexts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from lxml import etree
from pypdf import PdfReader

from odfa11y.audit import audit_odf
from odfa11y.odf import OdfDocument, Part, select_elements, validate
from odfa11y.pipeline import NativeOptions, export_document
from odfa11y.remediation import SetMetadata, remediate
from odfa11y.report import FactKeys

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURE = Path(__file__).parent / "reproductions/text-contexts.odt"


@pytest.mark.integration
def test_writer_revision_reload_and_rendered_word_boundaries(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    before = OdfDocument.open(FIXTURE)
    assert audit_odf(FIXTURE).facts[FactKeys.TEXT_HEADING_COUNT] == 1
    edited = tmp_path / "reviewed.odt"
    remediate(FIXTURE, edited, [SetMetadata(title="Reviewed context fixture")])
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
    export_document(edited, output, NativeOptions(soffice=soffice))
    text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
    assert re.search(r"One\s+Two\s+Three\s+Four", text)
    assert "Deleted heading" not in text
    assert "Note heading" in text
