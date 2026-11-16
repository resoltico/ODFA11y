# SPDX-License-Identifier: AGPL-3.0-only
"""A flat ODF document: all parts in one XML file."""

from pathlib import Path
lazy import os

from odfa11y.errors import MissingMemberError, PackageError
from odfa11y.odf.archive import MAX_UNCOMPRESSED_BYTES
from odfa11y.odf.storage import Layout, OdfStorage, Part
from odfa11y.publish import publish_file

FLAT_MEMBER = "document"


class FlatXmlStorage(OdfStorage):
    """One XML member holding meta, settings, styles and body; there is no manifest."""

    layout = Layout.FLAT

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
        return publish_file(destination, lambda stream: stream.write(self._data), replace=True)
