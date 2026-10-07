# SPDX-License-Identifier: MPL-2.0
"""Read the ``[text]`` table of a configuration into text operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from odfa11y.adapter import config_tables
from odfa11y.errors import ConfigError

from .graphics import AltText, SetAltText
from .linkify import LinkifyAddresses
from .remove_spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing
from .tables import HeaderRows, MarkHeaderRows

if TYPE_CHECKING:
    from odfa11y.adapter import Operation

TEXT_KEYS = {"remediation", "alt_text", "table_headers", "spacing"}


def parse_text_table(data: dict[str, object]) -> list[Operation]:
    """Turn the ``[text]`` table into operations in canonical order.

    Returns
    -------
    list[Operation]
        Remediation switches, alt text, table headers and spacing, in that order.

    """
    config_tables.known(data, TEXT_KEYS, "text")
    operations: list[Operation] = []
    operations += _remediation(config_tables.table(data, "remediation"))
    operations += _graphics(config_tables.table(data, "alt_text"))
    operations += _tables(config_tables.table(data, "table_headers"))
    operations += _spacing(config_tables.table(data, "spacing"))
    return operations


def _remediation(table: dict[str, object]) -> list[Operation]:
    config_tables.known(
        table, {"linkify_plain_addresses", "remove_empty_spacers"}, "text.remediation"
    )
    flags = config_tables.typed(table, bool, "text.remediation")
    operations: list[Operation] = []
    if flags.get("linkify_plain_addresses"):
        operations.append(LinkifyAddresses())
    if flags.get("remove_empty_spacers"):
        operations.append(RemoveEmptySpacers())
    return operations


def _graphics(table: dict[str, object]) -> list[Operation]:
    entries: dict[str, AltText] = {}
    for key in table:
        entry = config_tables.table(table, key)
        label = f"text.alt_text.{key}"
        config_tables.known(entry, {"title", "description", "fingerprint"}, label)
        texts = config_tables.typed(entry, str, label)
        entries[key] = AltText(
            texts.get("title"), texts.get("description"), texts.get("fingerprint")
        )
    return [SetAltText(entries)] if entries else []


def _tables(table: dict[str, object]) -> list[Operation]:
    entries: dict[str, HeaderRows] = {}
    for name, value in table.items():
        label = f"text.table_headers.{name}"
        if isinstance(value, dict):
            config_tables.known(value, {"rows", "fingerprint"}, label)
            rows = config_tables.typed({k: v for k, v in value.items() if k == "rows"}, int, label)
            texts = config_tables.typed(
                {k: v for k, v in value.items() if k == "fingerprint"}, str, label
            )
            count, fingerprint = rows.get("rows"), texts.get("fingerprint")
        else:
            count, fingerprint = (
                config_tables.typed({name: value}, int, "text.table_headers")[name],
                None,
            )
        if count is None or count < 1:
            msg = f"{label} must be a positive integer"
            raise ConfigError(msg)
        entries[name] = HeaderRows(count, fingerprint)
    return [MarkHeaderRows(entries)] if entries else []


def _spacing(table: dict[str, object]) -> list[Operation]:
    if not table:
        return []
    keys = {"reference_text", "target_styles", "exact_reference", "include_headings"}
    config_tables.known(table, keys, "text.spacing")
    reference = table.get("reference_text")
    targets = table.get("target_styles")
    if not isinstance(reference, str) or not reference:
        msg = "text.spacing.reference_text must be a non-empty string"
        raise ConfigError(msg)
    if (
        not isinstance(targets, list)
        or not targets
        or not all(isinstance(item, str) for item in targets)
    ):
        msg = "text.spacing.target_styles must be a non-empty list of strings"
        raise ConfigError(msg)
    flag_keys = ("exact_reference", "include_headings")
    flags = config_tables.typed(
        {key: table[key] for key in flag_keys if key in table}, bool, "text.spacing"
    )
    return [
        NormalizeSpacing(
            reference,
            tuple(cast("list[str]", targets)),
            exact_reference=flags.get("exact_reference", False),
            include_headings=flags.get("include_headings", False),
        )
    ]
