# SPDX-License-Identifier: MPL-2.0
"""Logical document target locations."""

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, unquote

from odfa11y.errors import PlanError
from odfa11y.serialization import record_dict
lazy from odfa11y.serialization import JsonObject


class Part(StrEnum):
    """A logical part of an ODF document, independent of how it is stored."""

    CONTENT = "content"
    STYLES = "styles"
    META = "meta"
    SETTINGS = "settings"
    MANIFEST = "manifest"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.CONTENT: "The logical document body contains the authored content.",
            self.STYLES: "The logical style part defines shared and master styles.",
            self.META: "The logical metadata part describes the document.",
            self.SETTINGS: "The logical settings part holds application settings.",
            self.MANIFEST: "The package manifest declares stored members and their media types.",
        }[self]


SEGMENT_PATTERN = (
    r"[A-Za-z][A-Za-z0-9_.-]*(?:\[(?:(?:name|id)="
    r"((?:[A-Za-z0-9_.~-]|%[0-9A-F]{2})*)|[1-9][0-9]*)\])?"
)
_SEGMENT = re.compile(SEGMENT_PATTERN + r"\Z")
_ROOTS = frozenset(part.value for part in Part) | {"package", "document"}
TARGET_PATH_PATTERN = (
    r"^(?:" + "|".join(sorted(_ROOTS)) + ")(?:/" + SEGMENT_PATTERN + r")*(?![\s\S])"
)


class TargetPath(str):
    """A canonical logical location, independent of package storage paths."""

    PATTERN = TARGET_PATH_PATTERN

    def __new__(cls, value: str) -> TargetPath:
        if type(value) is cls:
            return value
        if not isinstance(value, str):
            message = "A target path must be a string"
            raise PlanError(message)
        parts = value.split("/")
        if parts[0] not in _ROOTS:
            message = f"Invalid decision target: {value!r}"
            raise PlanError(message)
        for segment in parts[1:]:
            match = _SEGMENT.fullmatch(segment)
            if match is None or (
                match[1] is not None and quote(unquote(match[1]), safe="") != match[1]
            ):
                message = f"Decision target is not canonically encoded: {value!r}"
                raise PlanError(message)
        return super().__new__(cls, value)

    @classmethod
    def named(cls, part: str, element: str, name: str) -> TargetPath:
        return cls(f"{part}/{element}[name={quote(name, safe='')}]")

    @classmethod
    def indexed(cls, part: str, element: str, index: int) -> TargetPath:
        if type(index) is not int or index < 1:
            message = "A target ordinal must be a positive integer"
            raise PlanError(message)
        return cls(f"{part}/{element}[{index}]")


class Fingerprint(str):
    """A 64-bit identity for the reviewed content of one target."""

    LENGTH = 16
    PATTERN = r"^[0-9a-f]{" + str(LENGTH) + r"}(?![\s\S])"

    def __new__(cls, value: str) -> Fingerprint:
        if type(value) is cls:
            return value
        if not isinstance(value, str) or re.fullmatch(cls.PATTERN, value) is None:
            message = f"A target fingerprint requires {cls.LENGTH} lowercase hexadecimal digits"
            raise PlanError(message)
        return super().__new__(cls, value)

    @classmethod
    def of(cls, content: bytes) -> Fingerprint:
        return cls.from_digest(hashlib.sha256(content).hexdigest())

    @classmethod
    def from_digest(cls, digest: str) -> Fingerprint:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            message = "A fingerprint requires a complete lowercase SHA-256 digest"
            raise PlanError(message)
        return cls(digest[: cls.LENGTH])


@dataclass(frozen=True, slots=True)
class Target:
    """A logical target and the content identity to which its answer is bound."""

    path: TargetPath
    fingerprint: Fingerprint

    def __post_init__(self) -> None:
        if not isinstance(self.path, TargetPath) or not isinstance(self.fingerprint, Fingerprint):
            message = "A target requires a validated path and fingerprint"
            raise PlanError(message)
        if "/" not in self.path or self.path.partition("/")[0] not in {part.value for part in Part}:
            message = f"Invalid decision target: {self.path!r}"
            raise PlanError(message)


@dataclass(frozen=True, slots=True, init=False)
class Location:
    """Where a finding applies, independent of how the document is stored.

    ``path`` is logical: a part of the document, optionally narrowed by ``/``-separated
    segments such as ``paragraph[3]``. ``member`` names the stored package member and is set
    only where that physical detail helps, for example for a package-level defect.
    """

    path: TargetPath
    member: str | None = None

    def __init__(self, path: str | TargetPath, member: str | None = None) -> None:
        object.__setattr__(self, "path", TargetPath(path))
        object.__setattr__(self, "member", member)

    @classmethod
    def named(cls, part: str, element: str, name: str) -> Location:
        """Create an unambiguous named logical location.

        Returns
        -------
        Location
            A URI-escaped name within the given document part.

        """
        return cls(TargetPath.named(part, element, name))

    @classmethod
    def indexed(cls, part: str, element: str, index: int) -> Location:
        """Create an ordinal logical location.

        Returns
        -------
        Location
            A one-based element ordinal in its part.

        """
        return cls(TargetPath.indexed(part, element, index))

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


FINGERPRINT_PATTERN = Fingerprint.PATTERN


def require_target(target: Target | None) -> Target:
    """Return a content-bound target when a targeted editor requires one."""
    if target is None:
        message = "A target-scoped decision requires a reviewed target"
        raise PlanError(message)
    return target
