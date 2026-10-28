# SPDX-License-Identifier: MPL-2.0
"""Published JSON schemas shipped with the installed package."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING, cast

from odfa11y.errors import ReportError

if TYPE_CHECKING:
    from odfa11y.serialization import JsonObject


def read_schema(name: str) -> JsonObject:
    """Read one packaged schema by its format name.

    Returns
    -------
    JsonObject
        The Draft 2020-12 schema, without network access.

    Raises
    ------
    ReportError
        The name is unknown or unsafe.

    """
    resource = files(__package__).joinpath(f"{name}.schema.json")
    if not name.isidentifier() or not resource.is_file():
        msg = f"Unknown JSON schema: {name!r}"
        raise ReportError(msg)
    return cast("JsonObject", json.loads(resource.read_text(encoding="utf-8")))
