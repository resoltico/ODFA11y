# SPDX-License-Identifier: MPL-2.0
"""Read the ``[text]`` table of a configuration into text operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from odfa11y.adapter import config_tables
from odfa11y.content import GraphicDescription
from odfa11y.errors import ConfigError

from .graphics import SetGraphicDescriptions
from .headings import MAX_HEADING_LEVEL, HeadingLevel, SetHeadingLevels
from .linkify import LinkifyAddresses
from .remove_spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing
from .tables import MarkTableHeaders, TableHeaders

if TYPE_CHECKING:
    from odfa11y.adapter import Operation

TEXT_KEYS = {"remediation", "graphics", "table_headers", "spacing", "heading_levels"}


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
    operations += _graphics(config_tables.table(data, "graphics"))
    operations += _headings(config_tables.table(data, "heading_levels"))
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
    entries: dict[str, GraphicDescription] = {}
    for key in table:
        entry = config_tables.table(table, key)
        label = f"text.graphics.{key}"
        config_tables.known(entry, {"title", "description", "fingerprint"}, label)
        texts = config_tables.typed(entry, str, label)
        entries[key] = GraphicDescription(
            texts.get("title"), texts.get("description"), texts.get("fingerprint")
        )
    return [SetGraphicDescriptions(entries)] if entries else []


def _tables(table: dict[str, object]) -> list[Operation]:
    entries: dict[str, TableHeaders] = {}
    for name in table:
        label = f"text.table_headers.{name}"
        value = config_tables.table(table, name)
        config_tables.known(value, {"rows", "columns", "fingerprint"}, label)
        counts = config_tables.typed(
            {k: v for k, v in value.items() if k in {"rows", "columns"}}, int, label
        )
        fingerprint = config_tables.typed(
            {k: v for k, v in value.items() if k == "fingerprint"}, str, label
        ).get("fingerprint")
        if not counts or any(count < 1 for count in counts.values()):
            msg = f"{label} must contain positive rows or columns"
            raise ConfigError(msg)
        entries[name] = TableHeaders(counts.get("rows"), counts.get("columns"), fingerprint)
    return [MarkTableHeaders(entries)] if entries else []


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


def _headings(table: dict[str, object]) -> list[Operation]:
    entries = {}
    for target in table:
        value = config_tables.table(table, target)
        label = f"text.heading_levels.{target}"
        config_tables.known(value, {"level", "fingerprint"}, label)
        levels = config_tables.typed({k: v for k, v in value.items() if k == "level"}, int, label)
        fingerprints = config_tables.typed(
            {k: v for k, v in value.items() if k == "fingerprint"}, str, label
        )
        level = levels.get("level")
        if level is None or not 1 <= level <= MAX_HEADING_LEVEL:
            msg = f"{label}.level must be an integer from 1 to 10"
            raise ConfigError(msg)
        entries[target] = HeadingLevel(level, fingerprints.get("fingerprint"))
    return [SetHeadingLevels(entries)] if entries else []
