# SPDX-License-Identifier: MPL-2.0
"""Logical document target locations."""

from dataclasses import dataclass
from urllib.parse import quote

from odfa11y.serialization import record_dict
lazy from odfa11y.serialization import JsonObject


@dataclass(frozen=True, slots=True)
class Location:
    """Where a finding applies, independent of how the document is stored.

    ``path`` is logical: a part of the document, optionally narrowed by ``/``-separated
    segments such as ``paragraph[3]``. ``member`` names the stored package member and is set
    only where that physical detail helps, for example for a package-level defect.
    """

    path: str
    member: str | None = None

    @classmethod
    def named(cls, part: str, element: str, name: str) -> Location:
        """Create an unambiguous named logical location.

        Returns
        -------
        Location
            A URI-escaped name within the given document part.

        """
        return cls(f"{part}/{element}[name={quote(name, safe='')}]")

    @classmethod
    def indexed(cls, part: str, element: str, index: int) -> Location:
        """Create an ordinal logical location.

        Returns
        -------
        Location
            A one-based element ordinal in its part.

        """
        return cls(f"{part}/{element}[{index}]")

    @property
    def label(self) -> str:
        """The path, followed by the member in parentheses when there is one."""
        return self.path if self.member is None else f"{self.path} ({self.member})"

    def as_dict(self) -> JsonObject:
        """Serialize the typed record.

        Returns
        -------
        JsonObject
            The published JSON fields.

        """
        return record_dict(self)
