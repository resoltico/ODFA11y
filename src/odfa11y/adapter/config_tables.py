# SPDX-License-Identifier: MPL-2.0
"""Validate the shape of TOML tables: shared by the core and by every family's config."""

from __future__ import annotations

from typing import cast

from odfa11y.errors import PlanError


def table(data: dict[str, object], key: str) -> dict[str, object]:
    """Read an optional sub-table.

    Returns
    -------
    dict[str, object]
        The table, or an empty one when absent.

    Raises
    ------
    PlanError
        The value exists but is not a table.

    """
    value = data.get(key, {})
    if not isinstance(value, dict):
        msg = f"[{key}] must be a table"
        raise PlanError(msg)
    return value


def known(data: dict[str, object], allowed: set[str], label: str) -> None:
    """Reject keys outside an allowed set.

    Raises
    ------
    PlanError
        The table has keys that are not allowed.

    """
    unknown = data.keys() - allowed
    if unknown:
        msg = f"Unknown {label} keys: {', '.join(sorted(unknown))}"
        raise PlanError(msg)


def typed[T](data: dict[str, object], expected: type[T], label: str) -> dict[str, T]:
    """Require every value to be exactly of one type (a boolean is not an integer).

    Returns
    -------
    dict[str, T]
        The same keys with values narrowed to ``expected``.

    Raises
    ------
    PlanError
        A value has another type.

    """
    values: dict[str, T] = {}
    for key, value in data.items():
        if type(value) is not expected:
            msg = f"{label}.{key} must be {expected.__name__}"
            raise PlanError(msg)
        values[key] = cast("T", value)
    return values
