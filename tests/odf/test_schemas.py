# SPDX-License-Identifier: MPL-2.0
"""Published schemas reject invalid formats and facts and match generated authorities."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from odfa11y.contracts import encode
from odfa11y.errors import InvalidOption
from odfa11y.families import REGISTRY
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from tests.fixtures.schema import read_schema
from tools.generate_reference import schemas


@pytest.mark.parametrize("name", ["report", "run", "batch", "doctor", "remediation", "plan"])
def test_shipped_schema_is_current_and_valid(name: str) -> None:
    schema = read_schema(name)
    assert schema == schemas()[name]
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("change", ["format", "unknown", "count", "obsolete"])
def test_report_schema_detects_wrong_format_fields_and_measurement_types(change: str) -> None:
    report = Report[object](
        kind=ReportKind.PDF, subject="sample.pdf", facts=(PdfMeasurements(page_count=1),)
    )
    payload = deepcopy(report.as_dict())
    if change == "format":
        payload["format"] = 5
    elif change == "obsolete":
        payload["metadata"] = {}
    else:
        facts = payload["facts"]
        assert isinstance(facts, list)
        row = facts[0]
        assert isinstance(row, dict)
        row["arbitrary" if change == "unknown" else "page_count"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(read_schema("report")).validate(payload)


@pytest.mark.parametrize("name", ["../report", "/report", "missing"])
def test_unknown_schema_paths_are_refused(name: str) -> None:
    with pytest.raises(InvalidOption, match="Unknown JSON schema"):
        read_schema(name)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_cannot_be_published_as_json(number: float) -> None:
    with pytest.raises(InvalidOption, match="Non-finite"):
        encode({"measurement": number})


def test_generated_schemas_do_not_depend_on_family_registry_insertion_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = schemas()
    original = list(REGISTRY.items())
    with monkeypatch.context() as patch:
        patch.setattr("odfa11y.plans.registry.REGISTRY", dict(reversed(original)))
        assert schemas() == before
