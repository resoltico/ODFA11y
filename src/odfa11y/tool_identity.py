# SPDX-License-Identifier: MPL-2.0
"""The name and version reported by an external tool."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Name and version of an application as it reports itself."""

    name: str
    version: str

    def as_dict(self) -> dict[str, str]:
        """Serialize the identity.

        Returns
        -------
        dict[str, str]
            The tool name and version.
        """
        return {"name": self.name, "version": self.version}
