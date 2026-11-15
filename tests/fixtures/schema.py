# SPDX-License-Identifier: MPL-2.0
"""Validate published record payloads explicitly in contract tests."""

import json
from importlib.resources import files
from typing import Protocol, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.protocols import Validator

from odfa11y.contracts import JsonObject
from odfa11y.errors import InvalidOption
from odfa11y.plans import Plan
from odfa11y.plans.registry import registered_formats
from odfa11y.schemas import registered_contracts
from tools.generate_reference import FORMATS


def read_schema(name: str) -> JsonObject:
    if name not in {contract.name for contract in registered_contracts()}:
        message = f"Unknown JSON schema: {name!r}"
        raise InvalidOption(message)
    resource = files("odfa11y.schemas").joinpath(name + ".schema.json")
    return cast(JsonObject, json.loads(resource.read_text(encoding="utf-8")))


FORMAT_CHECKER = FormatChecker()
for format_name, format_validator in registered_formats().items():
    FORMAT_CHECKER.checks(format_name)(format_validator)


RECORD_VALIDATORS: dict[object, Validator] = {
    record_type: Draft202012Validator(read_schema(name), format_checker=FORMAT_CHECKER)
    for name, record_type in FORMATS.items()
}


class PublishedRecord(Protocol):
    def as_dict(self) -> JsonObject: ...


def assert_record_schema(record: PublishedRecord) -> JsonObject:
    """Validate a real serialization against its separately generated schema."""
    payload = record.as_dict()
    if isinstance(record, Plan):
        Draft202012Validator(read_schema("plan-file"), format_checker=FORMAT_CHECKER).validate(
            payload
        )
    else:
        RECORD_VALIDATORS[type(record)].validate(payload)
    return payload
