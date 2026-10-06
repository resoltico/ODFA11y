# SPDX-License-Identifier: MPL-2.0
"""Validate explicit document remediation choices from TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .remediation_models import AltText, RemediationOptions


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
    _field_types(document, str, "document")
    fixes = _config_table(data, "remediation")
    _known_keys(fixes, {"linkify_plain_addresses", "remove_empty_spacers"}, "remediation")
    _field_types(fixes, bool, "remediation")
    headers = _config_table(data, "table_headers")
    _field_types(headers, int, "table_headers")
    for name, count in headers.items():
        if count < 1:
            msg = f"table_headers.{name} must be a positive integer"
            raise ValueError(msg)
    graphics = _config_table(data, "alt_text")
    alt_text = {
        key: _validate_alt_text(_config_table(graphics, key), f"alt_text.{key}") for key in graphics
    }
    return RemediationOptions(
        target_version=document.get("target_version", "1.4"),
        title=document.get("title"),
        description=document.get("description"),
        language=document.get("language"),
        linkify_plain_addresses=fixes.get("linkify_plain_addresses", False),
        remove_empty_spacers=fixes.get("remove_empty_spacers", False),
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


def _field_types(data: dict[str, object], expected: type, label: str) -> None:
    for key, value in data.items():
        if type(value) is not expected:
            msg = f"{label}.{key} must be {expected.__name__}"
            raise ValueError(msg)


def _validate_alt_text(data: dict[str, object], label: str) -> AltText:
    _known_keys(data, {"title", "description"}, label)
    _field_types(data, str, label)
    return AltText(title=data.get("title"), description=data.get("description"))
