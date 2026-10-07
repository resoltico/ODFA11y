# SPDX-License-Identifier: MPL-2.0
"""A parsed ODT document: trees parsed once, edits tracked, only edited members rewritten."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from .package import OdtPackage
from .styles import StyleCatalog
from .text import visible_text_snapshot

if TYPE_CHECKING:
    from os import PathLike
    from pathlib import Path


class OdtDocument:
    """Share one set of parsed XML trees between checks and operations.

    Read with :meth:`tree`; call :meth:`edit` before changing a member so that only
    edited members are re-serialized and untouched members stay byte-identical.
    """

    def __init__(self, package: OdtPackage) -> None:
        """Wrap a loaded package; XML members are parsed on first use."""
        self.package = package
        self._trees: dict[str, etree._ElementTree] = {}
        self._dirty: set[str] = set()
        self._edits = 0
        self._catalog: StyleCatalog | None = None

    @classmethod
    def open(cls, source: str | PathLike[str]) -> OdtDocument:
        """Load a document from an ODT file.

        Returns
        -------
        OdtDocument
            The document with no member parsed yet.

        """
        return cls(OdtPackage(source))

    def has(self, name: str) -> bool:
        """Return whether the package contains a member.

        Returns
        -------
        bool
            Whether the member exists.

        """
        return self.package.has(name)

    def tree(self, name: str) -> etree._ElementTree:
        """Return a member's parsed tree for reading.

        Returns
        -------
        etree._ElementTree
            The cached tree, parsed securely on first access.

        """
        if name not in self._trees:
            self._trees[name] = self.package.parse_xml(name)
        return self._trees[name]

    def edit(self, name: str) -> etree._ElementTree:
        """Return a member's tree for modification and record it as edited.

        Returns
        -------
        etree._ElementTree
            The cached tree.

        """
        tree = self.tree(name)
        self._dirty.add(name)
        self._edits += 1
        return tree

    @property
    def dirty(self) -> frozenset[str]:
        """Members that were opened for editing."""
        return frozenset(self._dirty)

    @property
    def edit_count(self) -> int:
        """How many times :meth:`edit` has been called."""
        return self._edits

    @property
    def catalog(self) -> StyleCatalog:
        """The style catalog over the live content and styles trees."""
        if self._catalog is None:
            self._catalog = StyleCatalog(self.tree("content.xml"), self.tree("styles.xml"))
        return self._catalog

    def text_snapshot(self) -> tuple[str, ...]:
        """Collect normalized visible text from the live content tree.

        Returns
        -------
        tuple[str, ...]
            One entry per heading or paragraph.

        """
        return visible_text_snapshot(self.tree("content.xml"))

    def save(self, destination: str | PathLike[str]) -> Path:
        """Serialize edited members and atomically publish the package.

        Returns
        -------
        Path
            The saved destination.

        """
        for name in self._trees:
            if name in self._dirty:
                payload = etree.tostring(
                    self._trees[name].getroot(),
                    xml_declaration=True,
                    encoding="UTF-8",
                    standalone=None,
                )
                self.package.write_member(name, payload)
        return self.package.save(destination)
