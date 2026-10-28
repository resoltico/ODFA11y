# SPDX-License-Identifier: MPL-2.0
"""Detect live XML changes by content and keep derived state coherent between operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from lxml import etree

from odfa11y.errors import MissingMemberError, PackageError

from .access import require_access
from .detect import detect
from .opening import open_storage
from .protection import inspect_protection
from .storage import Part, parse_member_xml

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from os import PathLike
    from pathlib import Path

    from .access import Use
    from .detect import Detection
    from .kinds import DocumentKind
    from .storage import OdfStorage


@dataclass(frozen=True, slots=True)
class DocumentCheckpoint:
    """The observed live XML and stored-member identities at an operation boundary."""

    trees: dict[str, str]
    members: dict[str, str]


def _tree_digest(tree: etree._ElementTree) -> str:
    # C14N 2.0 discards namespace bindings used only by QName-valued attributes.
    return hashlib.sha256(etree.tostring(tree, encoding="UTF-8")).hexdigest()


class OdfDocument:
    """Share one set of parsed XML trees between checks and operations.

    Mutations through :meth:`tree` are detected from serialized content, including
    namespace bindings used only by attribute values. Untouched members stay byte-identical.
    Checkpoints invalidate derived caches at operation boundaries.
    """

    def __init__(self, storage: OdfStorage) -> None:
        """Wrap storage, inspect protection, and parse semantic XML parts on first use."""
        self.storage = storage
        self.protection = inspect_protection(storage)
        self._trees: dict[str, etree._ElementTree] = {}
        self._original: dict[str, str] = {}
        self._parsed_sources: dict[str, str] = {}
        self._observed: dict[str, str] = {}
        self._initial_members = self._member_digests()
        self._detection: Detection | None = None
        self._derived: dict[str, object] = {}

    @classmethod
    def open(cls, source: str | PathLike[str]) -> OdfDocument:
        """Load a document from an ODF package or flat XML file.

        Returns
        -------
        OdfDocument
            The document with manifest protection inspected and semantic parts parsed lazily.

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
            payload = self.storage.read(name)
            self._trees[name] = parse_member_xml(name, payload)
            digest = _tree_digest(self._trees[name])
            self._original[name] = digest
            self._parsed_sources[name] = hashlib.sha256(payload).hexdigest()
            self._observed[name] = digest
        return self._trees[name]

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
        """XML members whose live or stored content differs from the initial view."""
        return self.changed_since(DocumentCheckpoint({}, self._initial_members))

    def require(self, use: Use) -> None:
        """Establish one protected-content access policy before semantic work.

        The shared access policy raises PackageError for blocked package views.

        """
        require_access(self.protection, use)
        self.checkpoint()

    def checkpoint(self) -> DocumentCheckpoint:
        """Capture XML content and invalidate derived state after observed mutations.

        Returns
        -------
        DocumentCheckpoint
            Digests of live trees and stored standard XML members.

        Raises
        ------
        PackageError
            Stored XML was replaced behind an already parsed tree.

        """
        members = self._member_digests()
        if any(members.get(name) != digest for name, digest in self._parsed_sources.items()):
            msg = "Stored XML changed behind a cached tree; reopen the document before proceeding."
            raise PackageError(msg)
        trees = {name: _tree_digest(tree) for name, tree in self._trees.items()}
        if any(self._observed.get(name) != digest for name, digest in trees.items()):
            self._derived.clear()
            self._detection = None
        self._observed = trees.copy()
        return DocumentCheckpoint(trees, members)

    def changed_since(self, before: DocumentCheckpoint) -> frozenset[str]:
        """Compare actual XML content, without treating lazy parsing as an edit.

        Returns
        -------
        frozenset[str]
            Members with changed live trees or stored XML bytes.

        """
        current = self.checkpoint()
        changed = {
            name
            for name, digest in current.trees.items()
            if digest != before.trees.get(name, self._original[name])
        }
        changed.update(
            name
            for name in before.members.keys() | current.members.keys()
            if before.members.get(name) != current.members.get(name)
        )
        return frozenset(changed)

    def _member_digests(self) -> dict[str, str]:
        names = {name for part in Part if (name := self.member_name(part)) is not None}
        return {name: hashlib.sha256(self.storage.read(name)).hexdigest() for name in names}

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
        """Return family state cached for the observed tree generation.

        Returns
        -------
        T
            The cached value for ``key``.

        """
        if key not in self._derived:
            self._derived[key] = factory()
        return cast("T", self._derived[key])

    def save(self, destination: str | PathLike[str]) -> Path:
        """Serialize edited members and atomically publish the document.

        Returns
        -------
        Path
            The saved destination.

        """
        current = self.checkpoint()
        for name, tree in self._trees.items():
            if current.trees[name] != self._original[name]:
                payload = etree.tostring(
                    tree,
                    xml_declaration=True,
                    encoding="UTF-8",
                    standalone=None,
                )
                self.storage.write_member(name, payload)
                self._parsed_sources[name] = hashlib.sha256(payload).hexdigest()
        return self.storage.save(destination)
