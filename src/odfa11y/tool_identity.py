# SPDX-License-Identifier: MPL-2.0
"""The name and version reported by an external tool."""

from dataclasses import dataclass

from odfa11y.contracts import JsonObject, record_dict


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Name and version of an application as it reports itself."""

    name: str
    version: str

    def as_dict(self) -> JsonObject:
        """Serialize the identity.

        Returns
        -------
        JsonObject
            The tool name and version.
        """
        return record_dict(self)
