# SPDX-License-Identifier: MPL-2.0
"""Read the TOML configuration: remediation operations plus the fidelity policy."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from odfa11y.errors import ConfigError
from odfa11y.fidelity import PAGINATION_MODES, FidelityPolicy
from odfa11y.odf import SUPPORTED_VERSIONS
from odfa11y.remediation import (
    AltText,
    LinkifyAddresses,
    MarkHeaderRows,
    NormalizeSpacing,
    RemoveEmptySpacers,
    SetAltText,
    SetMetadata,
    SetOdfVersion,
)

if TYPE_CHECKING:
    from odfa11y.remediation import (
        Operation,
    )

MAX_CHANNEL_VALUE = 255
TOP_LEVEL = {"document", "remediation", "table_headers", "alt_text", "spacing", "fidelity"}


@dataclass(frozen=True, slots=True)
class Config:
    """Validated choices: operations in their fixed order, and the fidelity policy."""

    operations: tuple[Operation, ...] = ()
    fidelity: FidelityPolicy = field(default_factory=FidelityPolicy)


def load_config(path: str | Path) -> Config:
    """Load and validate a configuration file.

    Returns
    -------
    Config
        Operations in canonical order and the fidelity policy.

    Raises
    ------
    ConfigError
        The file is unreadable or invalid TOML, or a key, type or value is not supported.

    """
    try:
        with Path(path).open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        msg = f"Cannot read configuration {path}: {exc}"
        raise ConfigError(msg) from exc
    _known(data, TOP_LEVEL, "configuration")
    operations: list[Operation] = []
    operations += _document(_table(data, "document"))
    operations += _remediation(_table(data, "remediation"))
    operations += _graphics(_table(data, "alt_text"))
    operations += _tables(_table(data, "table_headers"))
    operations += _spacing(_table(data, "spacing"))
    return Config(tuple(operations), _fidelity(_table(data, "fidelity")))


def _document(table: dict[str, object]) -> list[Operation]:
    _known(table, {"title", "description", "language", "odf_version"}, "document")
    texts = _typed(table, str, "document")
    operations: list[Operation] = []
    version = texts.get("odf_version")
    if version is not None:
        if version not in SUPPORTED_VERSIONS:
            msg = f"document.odf_version must be one of {', '.join(SUPPORTED_VERSIONS)}"
            raise ConfigError(msg)
        operations.append(SetOdfVersion(version))
    if {"title", "description", "language"} & texts.keys():
        operations.append(
            SetMetadata(texts.get("title"), texts.get("description"), texts.get("language"))
        )
    return operations


def _remediation(table: dict[str, object]) -> list[Operation]:
    _known(table, {"linkify_plain_addresses", "remove_empty_spacers"}, "remediation")
    flags = _typed(table, bool, "remediation")
    operations: list[Operation] = []
    if flags.get("linkify_plain_addresses"):
        operations.append(LinkifyAddresses())
    if flags.get("remove_empty_spacers"):
        operations.append(RemoveEmptySpacers())
    return operations


def _graphics(table: dict[str, object]) -> list[Operation]:
    entries: dict[str, AltText] = {}
    for key in table:
        entry = _table(table, key)
        _known(entry, {"title", "description"}, f"alt_text.{key}")
        texts = _typed(entry, str, f"alt_text.{key}")
        entries[key] = AltText(texts.get("title"), texts.get("description"))
    return [SetAltText(entries)] if entries else []


def _tables(table: dict[str, object]) -> list[Operation]:
    counts = _typed(table, int, "table_headers")
    for name, count in counts.items():
        if count < 1:
            msg = f"table_headers.{name} must be a positive integer"
            raise ConfigError(msg)
    return [MarkHeaderRows(counts)] if counts else []


def _spacing(table: dict[str, object]) -> list[Operation]:
    if not table:
        return []
    keys = {"reference_text", "target_styles", "exact_reference", "include_headings"}
    _known(table, keys, "spacing")
    reference = table.get("reference_text")
    targets = table.get("target_styles")
    if not isinstance(reference, str) or not reference:
        msg = "spacing.reference_text must be a non-empty string"
        raise ConfigError(msg)
    if (
        not isinstance(targets, list)
        or not targets
        or not all(isinstance(item, str) for item in targets)
    ):
        msg = "spacing.target_styles must be a non-empty list of strings"
        raise ConfigError(msg)
    flag_keys = ("exact_reference", "include_headings")
    flags = _typed({key: table[key] for key in flag_keys if key in table}, bool, "spacing")
    return [
        NormalizeSpacing(
            reference,
            tuple(cast("list[str]", targets)),
            exact_reference=flags.get("exact_reference", False),
            include_headings=flags.get("include_headings", False),
        )
    ]


def _fidelity(table: dict[str, object]) -> FidelityPolicy:
    _known(table, {"pagination", "raster_tolerance", "ink_threshold", "dpi"}, "fidelity")
    default = FidelityPolicy()
    pagination = table.get("pagination", default.pagination)
    if pagination not in PAGINATION_MODES:
        msg = f"fidelity.pagination must be one of {', '.join(PAGINATION_MODES)}"
        raise ConfigError(msg)
    tolerance = table.get("raster_tolerance", default.raster_tolerance)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
        msg = "fidelity.raster_tolerance must be a non-negative number"
        raise ConfigError(msg)
    integer_keys = ("ink_threshold", "dpi")
    integers = _typed({key: table[key] for key in integer_keys if key in table}, int, "fidelity")
    threshold = integers.get("ink_threshold", default.ink_threshold)
    dpi = integers.get("dpi", default.dpi)
    if not 0 <= threshold <= MAX_CHANNEL_VALUE or dpi < 1:
        msg = "fidelity.ink_threshold must be 0-255 and fidelity.dpi positive"
        raise ConfigError(msg)
    return FidelityPolicy(str(pagination), float(tolerance), threshold, dpi)


def _table(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        msg = f"[{key}] must be a table"
        raise ConfigError(msg)
    return value


def _known(data: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = data.keys() - allowed
    if unknown:
        msg = f"Unknown {label} keys: {', '.join(sorted(unknown))}"
        raise ConfigError(msg)


def _typed[T](data: dict[str, object], expected: type[T], label: str) -> dict[str, T]:
    values: dict[str, T] = {}
    for key, value in data.items():
        if type(value) is not expected:
            msg = f"{label}.{key} must be {expected.__name__}"
            raise ConfigError(msg)
        values[key] = cast("T", value)
    return values
