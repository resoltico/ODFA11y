# SPDX-License-Identifier: MPL-2.0
"""Producer contracts reject wrong measurement types before changing a report."""

from typing import cast

import pytest

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.contracts import decode
from odfa11y.errors import InvalidOption
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.pdf.fidelity.compare import FidelityMeasurements
from odfa11y.pdf.structure.checks import PdfStructureMeasurements
from odfa11y.report import Report, ReportKind
from tests.fixtures.measurements import measurement


@pytest.mark.parametrize(
    ("contract", "values"),
    [
        (PdfMeasurements, {"page_count": True}),
        (PdfMeasurements, {"page_count": 1.0}),
        (DocumentMetadata, {"title": 3}),
        (PdfStructureMeasurements, {"structure_tags": {"H1": "one"}}),
        (FidelityMeasurements, {"raster_changed_ratios": ["wrong"]}),
    ],
)
def test_wrong_measurement_types_are_refused(
    contract: type[object], values: dict[str, object]
) -> None:
    with pytest.raises(InvalidOption):
        decode(contract, values)


def test_invalid_fragments_cannot_replace_a_valid_measurement() -> None:
    report = Report[object](ReportKind.PDF, "sample.pdf")
    report.measure(PdfMeasurements(page_count=1))
    with pytest.raises(InvalidOption):
        report.measure(PdfMeasurements(page_count=cast(int, "wrong")))
    assert measurement(report, PdfMeasurements).page_count == 1
    with pytest.raises(TypeError, match="dataclass"):
        report.measure({"page_count": 2})


def test_closed_producer_fields_and_typed_records_replace_the_key_registry() -> None:
    with pytest.raises(InvalidOption, match="Unknown keys"):
        decode(PdfMeasurements, {"page_count": 1, "unknown_count": 2})
    report = Report[object](ReportKind.ODF, "sample.odt")
    report.measure(DocumentMetadata(title="Source"))
    report.measure(PdfMeasurements(title="Export"))
    assert isinstance(report.facts[0], DocumentMetadata)
    assert isinstance(report.facts[1], PdfMeasurements)
    values = report.as_dict()["facts"]
    assert isinstance(values, list)
    first, second = values
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first["title"] == "Source"
    assert second["title"] == "Export"
