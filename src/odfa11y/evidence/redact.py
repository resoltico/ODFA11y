# SPDX-License-Identifier: MPL-2.0
"""Keep local paths out of evidence: known locations become placeholders, the rest `<path>/name`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

# An absolute POSIX path of two or more segments, a Windows drive path, a UNC path, or a
# file:// URI. A single segment ("/Link") and URLs ("https://host/a") are left alone.
ABSOLUTE_PATH = re.compile(
    r"file:///[^\s'\"<>]+"
    r"|(?<![\w.:/~-])/(?:[\w.@+~-]+/)+[\w.@+~-]+"
    r"|\b[A-Za-z]:[\\/][^\s'\"<>]*"
    r"|\\\\[\w.$-]+\\[^\s'\"<>]+"
)


def _collapse(match: re.Match[str]) -> str:
    """Reduce an absolute path to its last segment.

    Returns
    -------
    str
        ``<path>/`` followed by the file name.

    """
    segment = re.split(r"[\\/]", match.group(0).rstrip("/\\"))[-1]
    return f"<path>/{segment}"


def _variants(path: Path) -> set[str]:
    found: set[str] = set()
    for candidate in (path, path.resolve()):
        found |= {str(candidate), candidate.as_posix()}
        found.add(candidate.as_uri() if candidate.is_absolute() else str(candidate))
    return {value for value in found if value and value not in {"/", "."}}


@dataclass(frozen=True, slots=True)
class Redactor:
    """Replace known local locations by placeholders, longest location first."""

    replacements: tuple[tuple[str, str], ...]

    @classmethod
    def for_locations(cls, locations: dict[str, Path]) -> Redactor:
        """Build a redactor for named locations.

        Any other absolute path (a home or temporary directory, a tool's location) is reduced
        to ``<path>/<file name>`` by :meth:`record`, so no directory name survives.

        Returns
        -------
        Redactor
            A redactor mapping every spelling of each location to ``<name>``.

        """
        pairs = [
            (spelling, f"<{name}>")
            for name, path in locations.items()
            for spelling in _variants(path)
        ]
        return cls(tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)))

    def text(self, value: str) -> str:
        """Replace known locations in raw text.

        Returns
        -------
        str
            The text with every known location replaced.

        """
        for spelling, placeholder in self.replacements:
            value = value.replace(spelling, placeholder)
        return value

    def record(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact every string of a JSON-shaped record, then any remaining absolute path.

        Returns
        -------
        dict[str, Any]
            A copy of the record in which no absolute path survives.

        """
        redacted = self._walk(data)
        return cast("dict[str, Any]", redacted)

    def _walk(self, value: object) -> object:
        if isinstance(value, str):
            return ABSOLUTE_PATH.sub(_collapse, self.text(value))
        if isinstance(value, dict):
            return {key: self._walk(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._walk(item) for item in value]
        return value
