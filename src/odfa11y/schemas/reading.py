# SPDX-License-Identifier: MPL-2.0
"""Read versioned JSON schema resources from the installed package."""

import json
from importlib.resources import files
from typing import cast

from odfa11y.errors import ReportError
lazy from odfa11y.serialization import JsonObject


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
