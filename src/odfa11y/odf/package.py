# SPDX-License-Identifier: MPL-2.0
"""Load, edit and atomically save ODT ZIP packages."""

from __future__ import annotations

import io
import lzma
import os
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.safe_xml import secure_xml_parser

from .archive import check_archive_limits, clone_zipinfo, validate_archive

if TYPE_CHECKING:
    from collections.abc import Iterable

ODT_MIMETYPE = "application/vnd.oasis.opendocument.text"
# Errors raised while reading malformed ZIP structure or decompressing damaged member data.
UNREADABLE_ARCHIVE_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    lzma.LZMAError,
    NotImplementedError,
)
REQUIRED_XML = ("content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml")


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
            raise ValueError(msg) from exc

    def _read_archive(self) -> None:
        with zipfile.ZipFile(self.source, "r") as zf:
            infos = zf.infolist()
            check_archive_limits(infos)
            for info in infos:
                self.order.append(info.filename)
                self.members[info.filename] = Member(info=info, data=zf.read(info))

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
        KeyError
            The requested member does not exist.

        """
        try:
            return self.members[name].data
        except KeyError as exc:
            msg = f"ODT member not found: {name}"
            raise KeyError(msg) from exc

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
        ValueError
            The member contains malformed XML.

        """
        data = self.read(name)
        try:
            root = etree.fromstring(data, parser=secure_xml_parser())
        except etree.XMLSyntaxError as exc:
            msg = f"Malformed XML in {name}: {exc}"
            raise ValueError(msg) from exc
        return etree.ElementTree(root)

    def write_xml(
        self,
        name: str,
        tree: etree._ElementTree | etree._Element,
        *,
        pretty_print: bool = False,
    ) -> None:
        """Serialize an XML tree into a package member."""
        root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
        payload = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=None,
            pretty_print=pretty_print,
        )
        self.write_member(name, payload)

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
        ValueError
            The package lacks mimetype or fails archive validation.

        """
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if "mimetype" not in self.members:
            msg = "Cannot write ODT without the required mimetype member"
            raise ValueError(msg)

        if len(self.order) != len(set(self.order)):
            msg = "Cannot rewrite an ODT package with duplicate ZIP member names"
            raise ValueError(msg)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
        )
        os.close(fd)
        tmp = Path(temp_name)
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

    def clone(self) -> OdtPackage:
        """Return an independent in-memory copy without writing to disk.

        Returns
        -------
        OdtPackage
            An independent copy of member bytes and ZIP metadata.

        """
        obj = object.__new__(OdtPackage)
        obj.source = self.source
        obj.order = list(self.order)
        obj.members = {
            name: Member(info=clone_zipinfo(member.info), data=bytes(member.data))
            for name, member in self.members.items()
        }
        return obj


def open_odt_from_bytes(data: bytes) -> zipfile.ZipFile:
    """Small test helper; callers should normally use :class:`OdtPackage`.

    Returns
    -------
    zipfile.ZipFile
        An opened ZIP archive; the caller must close it.

    """
    return zipfile.ZipFile(io.BytesIO(data), "r")
