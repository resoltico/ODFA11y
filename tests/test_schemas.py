# SPDX-License-Identifier: MPL-2.0
"""Published schemas reject invalid formats and facts and match generated authorities."""

from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from odfa11y.errors import ReportError
from odfa11y.report import FactKeys, FactSet, Report
from odfa11y.schemas import read_schema
from odfa11y.serialization import encode
from tools.generate_reference import schemas


@pytest.mark.parametrize("name", ["report", "run", "batch", "doctor", "remediation", "plan"])
def test_shipped_schema_is_current_and_valid(name: str) -> None:
    schema = read_schema(name)
    assert schema == schemas()[name]
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("change", ["format", "unknown", "count", "obsolete"])
def test_report_schema_detects_wrong_format_fields_and_measurement_types(change: str) -> None:
    report = Report(kind="pdf", subject="sample.pdf", facts=FactSet({FactKeys.PDF_PAGE_COUNT: 1}))
    payload = deepcopy(report.as_dict())
    if change == "format":
        payload["format"] = 5
    elif change == "obsolete":
        payload["metadata"] = {}
    else:
        facts = payload["facts"]
        assert isinstance(facts, dict)
        facts["arbitrary" if change == "unknown" else "pdf.page_count"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(read_schema("report")).validate(payload)


@pytest.mark.parametrize("name", ["../report", "/report", "missing"])
def test_unknown_schema_paths_are_refused(name: str) -> None:
    with pytest.raises(ReportError, match="Unknown JSON schema"):
        read_schema(name)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_cannot_be_published_as_json(number: float) -> None:
    with pytest.raises(ReportError, match="Non-finite"):
        encode({"measurement": number})
