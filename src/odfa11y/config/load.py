# SPDX-License-Identifier: MPL-2.0
"""Read the TOML configuration: remediation operations plus the fidelity policy."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.adapter import config_tables
from odfa11y.errors import ConfigError
from odfa11y.families import config_tables as family_tables
from odfa11y.fidelity import PAGINATION_MODES, FidelityPolicy
from odfa11y.odf import SUPPORTED_VERSIONS
from odfa11y.remediation import SetMetadata, SetOdfVersion

if TYPE_CHECKING:
    from odfa11y.adapter import Operation

MAX_CHANNEL_VALUE = 255
COMMON_TABLES = {"document", "fidelity"}


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
    families = family_tables()
    config_tables.known(data, COMMON_TABLES | families.keys(), "configuration")
    operations: list[Operation] = []
    operations += _document(config_tables.table(data, "document"))
    for name, parse in families.items():
        operations += parse(config_tables.table(data, name))
    return Config(tuple(operations), _fidelity(config_tables.table(data, "fidelity")))


def _document(table: dict[str, object]) -> list[Operation]:
    config_tables.known(table, {"title", "description", "language", "odf_version"}, "document")
    texts = config_tables.typed(table, str, "document")
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


def _fidelity(table: dict[str, object]) -> FidelityPolicy:
    config_tables.known(
        table, {"pagination", "raster_tolerance", "ink_threshold", "dpi"}, "fidelity"
    )
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
    integers = config_tables.typed(
        {key: table[key] for key in integer_keys if key in table}, int, "fidelity"
    )
    threshold = integers.get("ink_threshold", default.ink_threshold)
    dpi = integers.get("dpi", default.dpi)
    if not 0 <= threshold <= MAX_CHANNEL_VALUE or dpi < 1:
        msg = "fidelity.ink_threshold must be 0-255 and fidelity.dpi positive"
        raise ConfigError(msg)
    return FidelityPolicy(str(pagination), float(tolerance), threshold, dpi)
