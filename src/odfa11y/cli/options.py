# SPDX-License-Identifier: MPL-2.0
"""Cli options for ODF accessibility workflows."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from odfa11y.remediation import (
    AltText,
    RemediationOptions,
    load_remediation_config,
    validate_alt_text,
)

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


def options_from_args(args: argparse.Namespace) -> RemediationOptions:
    """Combine configuration-file choices with explicit command-line overrides.

    Returns
    -------
    RemediationOptions
        Options with every explicit override applied.

    Raises
    ------
    ValueError
        A configuration file or command-line value is invalid.

    """
    options = load_remediation_config(args.config) if args.config else RemediationOptions()

    overrides = {
        "target_version": args.target_version,
        "title": args.title,
        "description": args.description,
        "language": args.language,
        "linkify_plain_addresses": args.linkify,
        "remove_empty_spacers": args.remove_empty_spacers,
    }
    options = replace(
        options, **{key: value for key, value in overrides.items() if value is not None}
    )

    table_headers = dict(options.table_header_rows or {})
    for item in args.table_header:
        try:
            name, value = item.rsplit("=", 1)
            table_headers[name] = int(value)
        except (ValueError, TypeError) as exc:
            msg = f"Invalid --table-header {item!r}; expected TABLE=ROWS"
            raise ValueError(msg) from exc
    if table_headers:
        options = replace(options, table_header_rows=table_headers)

    if args.alt_map:
        mapping = _load_alt_map(args.alt_map)
        current = dict(options.alt_text or {})
        current.update(mapping)
        options = replace(options, alt_text=current)
    return options


def _load_alt_map(path: Path) -> dict[str, AltText]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "Alt-map JSON must be an object mapping frame/image identifiers to text."
        raise ValueError(msg)
    result: dict[str, AltText] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = AltText(description=value)
        elif isinstance(value, dict):
            result[key] = validate_alt_text(value, f"alt-map.{key}")
        else:
            msg = f"Alt-map value for {key!r} must be a string or object."
            raise ValueError(msg)
    return result
