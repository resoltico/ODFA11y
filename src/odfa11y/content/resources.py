# SPDX-License-Identifier: MPL-2.0
"""Resolve and identify local package resources without accessing external targets."""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from odfa11y.odf import PackageStorage, is_unsafe_member_name

if TYPE_CHECKING:
    from odfa11y.odf import OdfStorage

BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
SPACE_CODEPOINT = 32
DELETE_CODEPOINT = 127


def local_resource_path(href: str) -> str | None:
    """Decode a relative package URI, rejecting external, malformed or escaping paths.

    Returns
    -------
    str | None
        Normalized member path (``.`` for the package root), or None for other references.

    """
    if any(
        ord(character) <= SPACE_CODEPOINT or ord(character) == DELETE_CODEPOINT
        for character in href
    ):
        return None
    try:
        href.encode("utf-8", errors="strict")
        uri = urlsplit(href)
        if (
            uri.scheme
            or uri.netloc
            or "?" in href.partition("#")[0]
            or not uri.path
            or BAD_ESCAPE.search(href)
        ):
            return None
        unquote(uri.fragment, errors="strict")
        path = unquote(uri.path, errors="strict")
    except UnicodeError, ValueError:
        return None
    return _member_path(path)


def _member_path(path: str) -> str | None:
    """Normalize dot segments while preserving empty segments and confining the member.

    Returns
    -------
    str | None
        The normalized package path, or None for an unsafe member.

    """
    if (
        path.startswith("/")
        or "\\" in path
        or any(ord(char) < SPACE_CODEPOINT or ord(char) == DELETE_CODEPOINT for char in path)
    ):
        return None
    parts = []
    for part in path.split("/"):
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part != ".":
            parts.append(part)
    if path.endswith(("/.", "/..")):
        parts.append("")
    if parts and not parts[-1]:
        parts.pop()
    normalized = "/".join(parts) or "."
    return None if is_unsafe_member_name(normalized) else normalized


class ResourceIdentity:
    """Identify resource bytes once during a read-only audit or remediation preflight."""

    def __init__(self, storage: OdfStorage) -> None:
        """Index package member names without loading or hashing unreferenced resources."""
        self._storage = storage
        self._members = (
            sorted(storage.member_names()) if isinstance(storage, PackageStorage) else []
        )
        self._digests: dict[str, str] = {}
        self._references: dict[str, tuple[tuple[str, str], ...]] = {}

    def fingerprint(self, href: str) -> tuple[tuple[str, str], ...]:
        """Bind a local file or embedded-object directory to its complete named payloads.

        Returns
        -------
        tuple[tuple[str, str], ...]
            Member paths and SHA-256 digests; empty when the reference is not local or absent.

        """
        path = local_resource_path(href)
        if path is None:
            return ()
        if path not in self._references:
            names = [path] if self._storage.has(path) else []
            prefix = "" if path == "." else path + "/"
            index = bisect_left(self._members, prefix)
            while index < len(self._members) and self._members[index].startswith(prefix):
                names.append(self._members[index])
                index += 1
            for name in names:
                if name not in self._digests:
                    self._digests[name] = hashlib.sha256(self._storage.read(name)).hexdigest()
            self._references[path] = tuple((name, self._digests[name]) for name in names)
        return self._references[path]
