# SPDX-License-Identifier: MPL-2.0
"""Rule detail contracts reject undeclared data and bound diagnostic collections."""

import pytest

from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules
from odfa11y.rules.details import bounded_details


def test_diagnostic_truncation_applies_recursively_once() -> None:
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    report.raise_(rules.PKG009, details={"duplicates": ["x" * 5000] * 12})
    assert report.findings[0].details == {"duplicates": ["x" * 4096] * 8}
    assert bounded_details({"nested": {"rows": [{"value": "x" * 5000}] * 12}}) == {
        "nested": {"rows": [{"value": "x" * 4096}] * 8}
    }


@pytest.mark.parametrize("details", [{"undeclared": []}, {"duplicates": "wrong type"}])
def test_producer_must_honor_its_rule_detail_contract(details: dict[str, object]) -> None:
    report = Report(kind=ReportKind.ODF, subject="synthetic")
    with pytest.raises(ValueError, match="contract problem"):
        report.raise_(rules.PKG009, details=details)
    assert report.findings == []
