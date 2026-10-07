# SPDX-License-Identifier: MPL-2.0
"""Validate explicit document remediation choices from TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from .models import AltText, RemediationOptions


def load_remediation_config(path: str | Path) -> RemediationOptions:
    """Load remediation choices, rejecting unknown keys and incorrect types.

    Returns
    -------
    RemediationOptions
        Validated metadata and explicit structural remediation choices.

    Raises
    ------
    ValueError
        A key, table shape, field type or header-row count is invalid.

    """
    with Path(path).open("rb") as stream:
        data = tomllib.load(stream)
    _known_keys(data, {"document", "remediation", "table_headers", "alt_text"}, "configuration")
    document = _config_table(data, "document")
    _known_keys(document, {"target_version", "title", "description", "language"}, "document")
    texts = _typed_values(document, str, "document")
    fixes = _config_table(data, "remediation")
    _known_keys(fixes, {"linkify_plain_addresses", "remove_empty_spacers"}, "remediation")
    flags = _typed_values(fixes, bool, "remediation")
    headers = _typed_values(_config_table(data, "table_headers"), int, "table_headers")
    for name, count in headers.items():
        if count < 1:
            msg = f"table_headers.{name} must be a positive integer"
            raise ValueError(msg)
    graphics = _config_table(data, "alt_text")
    alt_text = {
        key: validate_alt_text(_config_table(graphics, key), f"alt_text.{key}") for key in graphics
    }
    return RemediationOptions(
        target_version=texts.get("target_version", "1.4"),
        title=texts.get("title"),
        description=texts.get("description"),
        language=texts.get("language"),
        linkify_plain_addresses=flags.get("linkify_plain_addresses", False),
        remove_empty_spacers=flags.get("remove_empty_spacers", False),
        table_header_rows=headers or None,
        alt_text=alt_text or None,
    )


def _config_table(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        msg = f"[{key}] must be a table"
        raise ValueError(msg)
    return value


def _known_keys(data: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = data.keys() - allowed
    if unknown:
        msg = f"Unknown {label} keys: {', '.join(sorted(unknown))}"
        raise ValueError(msg)


def _typed_values[T](data: dict[str, object], expected: type[T], label: str) -> dict[str, T]:
    values: dict[str, T] = {}
    for key, value in data.items():
        if type(value) is not expected:
            msg = f"{label}.{key} must be {expected.__name__}"
            raise ValueError(msg)
        values[key] = cast("T", value)
    return values


def validate_alt_text(data: dict[str, object], label: str) -> AltText:
    """Validate one alt-text table and build its replacement text.

    Returns
    -------
    AltText
        The validated title and description.

    """
    _known_keys(data, {"title", "description"}, label)
    texts = _typed_values(data, str, label)
    return AltText(title=texts.get("title"), description=texts.get("description"))
