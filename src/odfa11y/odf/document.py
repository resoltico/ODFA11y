# SPDX-License-Identifier: MPL-2.0
"""A parsed ODF document: trees parsed once, edits tracked, only edited members rewritten."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lxml import etree

from odfa11y.errors import MissingMemberError

from .detect import detect
from .opening import open_storage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from os import PathLike
    from pathlib import Path

    from .detect import Detection
    from .kinds import DocumentKind
    from .storage import OdfStorage, Part


class OdfDocument:
    """Share one set of parsed XML trees between checks and operations.

    Read with :meth:`tree`; call :meth:`edit` before changing a part so that only edited
    members are re-serialized and untouched members stay byte-identical.
    """

    def __init__(self, storage: OdfStorage) -> None:
        """Wrap a loaded storage; XML members are parsed on first use."""
        self.storage = storage
        self._trees: dict[str, etree._ElementTree] = {}
        self._dirty: set[str] = set()
        self._edits = 0
        self._detection: Detection | None = None
        self._derived: dict[str, Any] = {}

    @classmethod
    def open(cls, source: str | PathLike[str]) -> OdfDocument:
        """Load a document from an ODF package or flat XML file.

        Returns
        -------
        OdfDocument
            The document with no member parsed yet.

        """
        return cls(open_storage(source))

    @property
    def layout(self) -> str:
        """``package`` for a ZIP package, ``flat`` for a single XML file."""
        return self.storage.layout

    def member_name(self, part: Part) -> str | None:
        """Name the stored member that holds a part, if the document has it.

        Returns
        -------
        str | None
            The member name, or None when the part is absent.

        """
        name = self.storage.member_for(part)
        return name if name is not None and self.storage.has(name) else None

    def has(self, part: Part) -> bool:
        """Return whether the document has a part.

        Returns
        -------
        bool
            Whether the part exists.

        """
        return self.member_name(part) is not None

    def tree(self, part: Part) -> etree._ElementTree:
        """Return a part's parsed tree for reading.

        Returns
        -------
        etree._ElementTree
            The cached tree, parsed securely on first access.

        Raises
        ------
        MissingMemberError
            The document has no such part.

        """
        name = self.member_name(part)
        if name is None:
            msg = f"Document has no {part.value} part"
            raise MissingMemberError(msg)
        if name not in self._trees:
            self._trees[name] = self.storage.parse_xml(name)
        return self._trees[name]

    def edit(self, part: Part) -> etree._ElementTree:
        """Return a part's tree for modification and record its member as edited.

        Returns
        -------
        etree._ElementTree
            The cached tree.

        """
        tree = self.tree(part)
        name = self.member_name(part)
        if name is not None:
            self._dirty.add(name)
        self._edits += 1
        return tree

    def distinct_trees(self, *parts: Part) -> Iterator[etree._ElementTree]:
        """Yield each underlying tree once for the parts that exist.

        A flat document keeps several parts in one tree; this yields it once.

        Yields
        ------
        etree._ElementTree
            The trees in the order of their first part.

        """
        seen: set[str] = set()
        for part in parts:
            name = self.member_name(part)
            if name is not None and name not in seen:
                seen.add(name)
                yield self.tree(part)

    @property
    def dirty(self) -> frozenset[str]:
        """Members that were opened for editing."""
        return frozenset(self._dirty)

    @property
    def edit_count(self) -> int:
        """How many times :meth:`edit` has been called."""
        return self._edits

    @property
    def detection(self) -> Detection:
        """What the document declares itself to be."""
        if self._detection is None:
            self._detection = detect(self)
        return self._detection

    @property
    def kind(self) -> DocumentKind | None:
        """The document kind, or None when the media type is not an OpenDocument one."""
        return self.detection.kind

    def derived[T](self, key: str, factory: Callable[[], T]) -> T:
        """Return state a family derives from the live trees, creating it once.

        Returns
        -------
        T
            The cached value for ``key``.

        """
        if key not in self._derived:
            self._derived[key] = factory()
        return self._derived[key]

    def save(self, destination: str | PathLike[str]) -> Path:
        """Serialize edited members and atomically publish the document.

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
                self.storage.write_member(name, payload)
        return self.storage.save(destination)
