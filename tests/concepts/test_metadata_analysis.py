# SPDX-License-Identifier: AGPL-3.0-only
"""Typed metadata distinguishes original declarations from normalized language meaning."""

from pathlib import Path

from odfa11y.audit.metadata import audit_metadata
from odfa11y.concepts.metadata import read_metadata
from odfa11y.families import require_spec
from odfa11y.odf import OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.report import Report, ReportKind
from tests.fixtures.writer import make_minimal_odt


def test_equivalent_language_spellings_do_not_raise_a_mismatch(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt", language="en-US"))
    declared = next(document.tree(Part.META).iter(xml_names.DC_LANGUAGE))
    declared.text = " en_US "
    spec = require_spec(document.kind)
    assert spec.language is not None
    analysis = read_metadata(document, spec.language.read)
    assert analysis.declared == " en_US "
    assert analysis.metadata.language == "en-US"
    report = Report(ReportKind.ODF, "source.odt")
    assert audit_metadata(analysis, report) is analysis.metadata
    assert report.findings == []
