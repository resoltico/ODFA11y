# SPDX-License-Identifier: MPL-2.0
"""A flat ODF document: all parts in one XML file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import MissingMemberError, PackageError
from odfa11y.staging import staging_sibling

from .archive import MAX_UNCOMPRESSED_BYTES
from .storage import OdfStorage, Part

if TYPE_CHECKING:
    import os

FLAT_MEMBER = "document"


class FlatXmlStorage(OdfStorage):
    """One XML member holding meta, settings, styles and body; there is no manifest."""

    layout = "flat"

    def __init__(self, source: str | os.PathLike[str]) -> None:
        """Load the file, refusing one above the unpacked-size limit.

        Raises
        ------
        FileNotFoundError
            The source document does not exist.
        PackageError
            The file exceeds the size limit.

        """
        self.source = Path(source)
        if not self.source.is_file():
            raise FileNotFoundError(self.source)
        if self.source.stat().st_size > MAX_UNCOMPRESSED_BYTES:
            msg = f"Flat XML document exceeds the {MAX_UNCOMPRESSED_BYTES}-byte limit"
            raise PackageError(msg)
        self._data = self.source.read_bytes()

    def member_for(self, part: Part) -> str | None:
        """Name the member holding a part.

        Returns
        -------
        str | None
            The single member, or None for the manifest a flat document does not have.

        """
        return None if part is Part.MANIFEST else FLAT_MEMBER

    def has(self, name: str) -> bool:
        """Return whether the member exists.

        Returns
        -------
        bool
            True only for the single document member.

        """
        return name == FLAT_MEMBER

    def read(self, name: str) -> bytes:
        """Return the document bytes.

        Returns
        -------
        bytes
            The XML as stored.

        Raises
        ------
        MissingMemberError
            The name is not the document member.

        """
        if name != FLAT_MEMBER:
            msg = f"Flat document has no member {name!r}"
            raise MissingMemberError(msg)
        return self._data

    def write_member(self, name: str, data: bytes) -> None:
        """Replace the document bytes in memory.

        Raises
        ------
        MissingMemberError
            The name is not the document member.

        """
        if name != FLAT_MEMBER:
            msg = f"Flat document has no member {name!r}"
            raise MissingMemberError(msg)
        self._data = data

    def save(self, destination: str | os.PathLike[str]) -> Path:
        """Atomically publish the document.

        Returns
        -------
        Path
            The saved destination.

        """
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = staging_sibling(destination)
        try:
            staged.write_bytes(self._data)
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)
        return destination
