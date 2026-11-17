# SPDX-License-Identifier: AGPL-3.0-only
"""How an ODF document is stored, and the logical parts every layout provides."""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar
lazy import os
lazy from pathlib import Path

from lxml import etree

from odfa11y.errors import XmlParseError
from odfa11y.safe_xml import parse_secure
from odfa11y.targets import Part


class Layout(StrEnum):
    PACKAGE = "package"
    FLAT = "flat"

    @property
    def meaning(self) -> str:
        return {
            self.PACKAGE: "An OpenDocument ZIP package with separate members.",
            self.FLAT: "A single XML document containing the OpenDocument parts.",
        }[self]


class OdfStorage(ABC):
    """A loaded document container: a ZIP package or a single flat XML file."""

    layout: ClassVar[Layout]
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

        Malformed XML raises XmlParseError from the shared secure parser.

        """
        return parse_member_xml(name, self.read(name))


def parse_member_xml(name: str, data: bytes) -> etree._ElementTree:
    """Parse acquired member bytes with the common secure parser and contextual errors.

    Returns
    -------
    etree._ElementTree
        The parsed member tree.

    Raises
    ------
    XmlParseError
        The acquired member is not well-formed XML.

    """
    try:
        root = parse_secure(data)
    except etree.XMLSyntaxError as exc:
        msg = f"Malformed XML in {name}: {exc}"
        raise XmlParseError(msg) from exc
    return root.getroottree()
