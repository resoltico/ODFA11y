# SPDX-License-Identifier: MPL-2.0
"""How an ODF document is stored, and the logical parts every layout provides."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from lxml import etree

from odfa11y.errors import XmlParseError
from odfa11y.safe_xml import parse_secure

if TYPE_CHECKING:
    import os
    from pathlib import Path


class Part(StrEnum):
    """A logical part of an ODF document, independent of how it is stored."""

    CONTENT = "content"
    STYLES = "styles"
    META = "meta"
    SETTINGS = "settings"
    MANIFEST = "manifest"


class OdfStorage(ABC):
    """A loaded document container: a ZIP package or a single flat XML file."""

    layout: ClassVar[str]
    source: Path

    @abstractmethod
    def member_for(self, part: Part) -> str | None:
        """Name the stored member holding a part.

        Returns
        -------
        str | None
            The member name, or None when the layout has no such part.

        """

    @abstractmethod
    def has(self, name: str) -> bool:
        """Return whether a member exists.

        Returns
        -------
        bool
            Whether the member exists.

        """

    @abstractmethod
    def read(self, name: str) -> bytes:
        """Return a member's bytes.

        Returns
        -------
        bytes
            The member contents.

        """

    @abstractmethod
    def write_member(self, name: str, data: bytes) -> None:
        """Replace or add a member in memory."""

    @abstractmethod
    def save(self, destination: str | os.PathLike[str]) -> Path:
        """Validate and atomically publish the container.

        Returns
        -------
        Path
            The saved destination.

        """

    def parse_xml(self, name: str) -> etree._ElementTree:
        """Parse a member with entities and network access disabled.

        Returns
        -------
        etree._ElementTree
            The parsed tree.

        Raises
        ------
        XmlParseError
            The member is not well-formed XML.

        """
        try:
            root = parse_secure(self.read(name))
        except etree.XMLSyntaxError as exc:
            msg = f"Malformed XML in {name}: {exc}"
            raise XmlParseError(msg) from exc
        return etree.ElementTree(root)
