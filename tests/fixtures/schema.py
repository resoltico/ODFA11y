# SPDX-License-Identifier: MPL-2.0
"""Validate published record payloads explicitly in contract tests."""

from collections.abc import Callable
from typing import Protocol

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.protocols import Validator

from odfa11y.plans.registry import registered_formats
from odfa11y.schemas import read_schema
from odfa11y.serialization import JsonObject
from tools.generate_reference import FORMATS


def _format_test(validator: Callable[[str], object]) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if isinstance(value, str):
            validator(value)
        return True

    return check


FORMAT_CHECKER = FormatChecker()


for format_name, format_validator in registered_formats().items():
    FORMAT_CHECKER.checks(format_name, raises=ValueError)(_format_test(format_validator))


RECORD_VALIDATORS: dict[type[object], Validator] = {
    record_type: Draft202012Validator(read_schema(name), format_checker=FORMAT_CHECKER)
    for name, record_type in FORMATS.items()
}


class PublishedRecord(Protocol):
    def as_dict(self) -> JsonObject: ...


def assert_record_schema(record: PublishedRecord) -> JsonObject:
    """Validate a real serialization against its separately generated schema."""
    payload = record.as_dict()
    RECORD_VALIDATORS[type(record)].validate(payload)
    return payload
