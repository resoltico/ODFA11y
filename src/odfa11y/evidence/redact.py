# SPDX-License-Identifier: MPL-2.0
"""Keep local paths out of evidence: known locations become placeholders, the rest `<path>/name`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

# A path-looking run: a segment may contain single spaces ("My Documents"), so a directory
# named after a person cannot survive. Anchors: an absolute POSIX path of two or more
# segments, a Windows drive or UNC path, a file:// address, a home (~/) or parent (../) path.
SEGMENT = r"[^/\\\s'\"<>|:]+(?: [^/\\\s'\"<>|:]+)*"
ABSOLUTE_PATH = re.compile(
    r"file://[^\s'\"<>]+"
    rf"|(?<![\w.:/~>-])(?:~|\.\.)?/(?:{SEGMENT}/)+{SEGMENT}"
    rf"|(?<![\w.:/~>-])(?:~|\.\.)/{SEGMENT}"
    rf"|\b[A-Za-z]:[\\/](?:{SEGMENT}[\\/])*{SEGMENT}"
    rf"|\\\\[\w.$-]+\\(?:{SEGMENT}\\)*{SEGMENT}"
)
NAME_BOUNDARY = r"(?<![\w.-]){}(?![\w.-])"


def _collapse(match: re.Match[str]) -> str:
    """Reduce a path to its last segment.

    Returns
    -------
    str
        ``<path>/`` followed by the file name.

    """
    segment = re.split(r"[\\/]", match.group(0).rstrip("/\\"))[-1]
    return f"<path>/{segment}"


def _separator_blind(spelling: str) -> str:
    """Escape a location so a slash and a backslash match each other.

    Returns
    -------
    str
        A pattern that finds the location however its separators are written.

    """
    return r"[\\/]".join(re.escape(part) for part in re.split(r"[\\/]", spelling))


def _spellings(path: Path) -> set[str]:
    """List every absolute way a path may be written, resolved and not.

    Returns
    -------
    set[str]
        Native, POSIX and ``file://`` spellings; relative spellings are never included.

    """
    found: set[str] = set()
    for candidate in (path.absolute(), path.resolve()):
        found |= {str(candidate), candidate.as_posix(), candidate.as_uri()}
    return {value for value in found if len(value) > 1}


@dataclass(frozen=True, slots=True)
class Redactor:
    """Replace known local locations by placeholders, longest location first."""

    replacements: tuple[tuple[re.Pattern[str], str], ...]

    @classmethod
    def for_locations(cls, locations: dict[str, Path]) -> Redactor:
        """Build a redactor for named locations.

        Locations are replaced only where they stand as whole path prefixes, never inside a
        longer word or sibling directory. Any other absolute path (a home or temporary
        directory, a tool's location) is reduced to ``<path>/<file name>`` by :meth:`record`,
        so no directory name survives.

        Returns
        -------
        Redactor
            A redactor mapping every spelling of each location to ``<name>``.

        """
        pairs = sorted(
            (
                (spelling, f"<{name}>")
                for name, path in locations.items()
                for spelling in _spellings(path)
            ),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        return cls(
            tuple(
                (re.compile(NAME_BOUNDARY.format(_separator_blind(spelling))), placeholder)
                for spelling, placeholder in pairs
            )
        )

    def text(self, value: str) -> str:
        """Replace known locations in raw text.

        Returns
        -------
        str
            The text with every known location replaced.

        """
        for pattern, placeholder in self.replacements:
            value = pattern.sub(placeholder, value)
        return ABSOLUTE_PATH.sub(_collapse, value)

    def record(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact every string of a JSON-shaped record, keys included, then any other path.

        Returns
        -------
        dict[str, Any]
            A copy of the record in which no absolute path survives.

        """
        return cast("dict[str, Any]", self._walk(data))

    def _clean(self, value: str) -> str:
        return self.text(value)

    def _walk(self, value: object) -> object:
        if isinstance(value, str):
            return self._clean(value)
        if isinstance(value, dict):
            return {self._clean(str(key)): self._walk(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._walk(item) for item in value]
        return value
