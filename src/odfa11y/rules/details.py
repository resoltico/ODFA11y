# SPDX-License-Identifier: AGPL-3.0-only
"""One presentation truncation policy and annotation-owned detail contracts."""

from collections.abc import Mapping
from typing import Annotated

from odfa11y.contracts import ItemCount, JsonValue, Length, mapping_contract
from odfa11y.errors import DIAGNOSTIC_CHARACTERS

DETAIL_ITEMS = 8
DETAIL_CHARACTERS = DIAGNOSTIC_CHARACTERS


def detail_contract(name: str, fields: Mapping[str, object]) -> object:
    return mapping_contract(name + "Details", fields, total=False)


def bounded_details(values: Mapping[str, object]) -> dict[str, JsonValue]:
    return {key: _bounded(value) for key, value in values.items()}


def _bounded(value: object) -> JsonValue:
    if isinstance(value, str):
        return value[:DETAIL_CHARACTERS]
    if isinstance(value, Mapping):
        return {str(key): _bounded(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_bounded(item) for item in value[:DETAIL_ITEMS]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    message = "Finding details must use declared JSON-compatible values"
    raise TypeError(message)


type DetailText = Annotated[str, Length(maximum=DETAIL_CHARACTERS)]
type DetailList = Annotated[list[JsonValue], ItemCount(maximum=DETAIL_ITEMS)]
