# SPDX-License-Identifier: MPL-2.0
"""Inspect producer-owned measurement records in result assertions."""

from odfa11y.report import Report


def measurement[T](report: Report, expected: type[T]) -> T:
    records = [record for record in report.facts if isinstance(record, expected)]
    return records[0] if records else expected()


def measured[T](value: T | None) -> T:
    assert value is not None, "The producer did not measure the expected field"
    return value
