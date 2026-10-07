# SPDX-License-Identifier: MPL-2.0
"""Load, edit and atomically save ODT ZIP packages."""

from __future__ import annotations

import lzma
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.errors import MissingMemberError, PackageError, XmlParseError
from odfa11y.safe_xml import secure_xml_parser
from odfa11y.staging import staging_sibling

from .archive import (
    check_archive_limits,
    clone_zipinfo,
    is_unsafe_member_name,
    validate_archive,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

ODT_MIMETYPE = "application/vnd.oasis.opendocument.text"
# Errors raised while reading malformed or unsupported ZIP structure or damaged member data.
UNREADABLE_ARCHIVE_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    lzma.LZMAError,
    NotImplementedError,
    RuntimeError,  # ZIP-encrypted members
    zipfile.LargeZipFile,
)
REQUIRED_XML = ("content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml")


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read one member, treating I/O failures inside the archive as corruption.

    Returns
    -------
    bytes
        The decompressed member contents.

    Raises
    ------
    zipfile.BadZipFile
        The member's recorded location or data cannot be read.

    """
    try:
        return archive.read(info)
    except OSError as exc:
        msg = f"Cannot read member {info.filename!r}: {exc}"
        raise zipfile.BadZipFile(msg) from exc


@dataclass(slots=True)
class Member:
    """Preserve ZIP metadata alongside member contents."""

    info: zipfile.ZipInfo
    data: bytes


class OdtPackage:
    """In-memory ODT package that preserves member metadata when rewritten.

    ODF packages are ZIP files with one important packaging invariant: ``mimetype``
    must be the first member and must be stored without compression. This class
    makes that invariant explicit instead of relying on generic ZIP behaviour.
    """

    def __init__(self, source: str | os.PathLike[str]) -> None:
        """Load and index the document resources.

        Raises
        ------
        FileNotFoundError
            The source document does not exist.

        """
        self.source = Path(source)
        if not self.source.is_file():
            raise FileNotFoundError(self.source)
        self.members: dict[str, Member] = {}
        self.order: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            self._read_archive()
        except UNREADABLE_ARCHIVE_ERRORS as exc:
            msg = f"Not a valid ZIP/ODT package: {self.source}: {exc}"
            raise PackageError(msg) from exc

    def _read_archive(self) -> None:
        with zipfile.ZipFile(self.source, "r") as zf:
            infos = zf.infolist()
            check_archive_limits(infos)
            for info in infos:
                self.order.append(info.filename)
                self.members[info.filename] = Member(info=info, data=_read_member(zf, info))

    def has(self, name: str) -> bool:
        """Return whether the package contains a named member.

        Returns
        -------
        bool
            Whether the member exists.

        """
        return name in self.members

    def read(self, name: str) -> bytes:
        """Return the bytes of a required member.

        Returns
        -------
        bytes
            The member contents.

        Raises
        ------
        MissingMemberError
            The requested member does not exist.

        """
        try:
            return self.members[name].data
        except KeyError as exc:
            msg = f"ODT member not found: {name}"
            raise MissingMemberError(msg) from exc

    def write_member(self, name: str, data: bytes) -> None:
        """Replace or append a member in memory."""
        if name in self.members:
            self.members[name].data = data
            return
        info = zipfile.ZipInfo(name)
        info.compress_type = zipfile.ZIP_DEFLATED
        self.members[name] = Member(info=info, data=data)
        self.order.append(name)

    def parse_xml(self, name: str) -> etree._ElementTree:
        """Parse a member with external entities and network access disabled.

        Returns
        -------
        etree._ElementTree
            The securely parsed member tree.

        Raises
        ------
        XmlParseError
            The member contains malformed XML.

        """
        data = self.read(name)
        try:
            root = etree.fromstring(data, parser=secure_xml_parser())
        except etree.XMLSyntaxError as exc:
            msg = f"Malformed XML in {name}: {exc}"
            raise XmlParseError(msg) from exc
        return etree.ElementTree(root)

    def member_names(self) -> Iterable[str]:
        """Return member names in archive order.

        Returns
        -------
        Iterable[str]
            Member names in original archive order.

        """
        return tuple(self.order)

    def save(self, destination: str | os.PathLike[str]) -> Path:
        """Validate a rewritten archive before atomically replacing the destination.

        Returns
        -------
        Path
            The saved destination path.

        Raises
        ------
        PackageError
            The package lacks mimetype, has duplicate or unsafe member names, or fails
            archive validation.

        """
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if "mimetype" not in self.members:
            msg = "Cannot write ODT without the required mimetype member"
            raise PackageError(msg)

        if len(self.order) != len(set(self.order)):
            msg = "Cannot rewrite an ODT package with duplicate ZIP member names"
            raise PackageError(msg)
        unsafe = sorted(name for name in self.order if is_unsafe_member_name(name))
        if unsafe:
            msg = f"Cannot rewrite an ODT package with unsafe member names: {unsafe}"
            raise PackageError(msg)

        tmp = staging_sibling(destination)
        try:
            self._write_archive(tmp)
            validate_archive(tmp, ODT_MIMETYPE)
            tmp.replace(destination)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        return destination

    def _write_archive(self, tmp: Path) -> None:
        with zipfile.ZipFile(tmp, "w") as zf:
            # ODF package requirement: first member, uncompressed.
            mt_member = self.members["mimetype"]
            mt_info = clone_zipinfo(mt_member.info)
            mt_info.filename = "mimetype"
            mt_info.compress_type = zipfile.ZIP_STORED
            zf.writestr(mt_info, mt_member.data, compress_type=zipfile.ZIP_STORED)

            for name in self.order:
                if name == "mimetype" or name not in self.members:
                    continue
                member = self.members[name]
                info = clone_zipinfo(member.info)
                # Keep the original compression method where possible.
                compress_type = info.compress_type
                if compress_type not in {
                    zipfile.ZIP_STORED,
                    zipfile.ZIP_DEFLATED,
                    zipfile.ZIP_BZIP2,
                    zipfile.ZIP_LZMA,
                }:
                    compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, member.data, compress_type=compress_type)

            # Include any newly created members that were not in the original order.
            known = set(self.order)
            for name, member in self.members.items():
                if name == "mimetype" or name in known:
                    continue
                info = clone_zipinfo(member.info)
                zf.writestr(info, member.data, compress_type=info.compress_type)
