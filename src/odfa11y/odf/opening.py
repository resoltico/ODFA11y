# SPDX-License-Identifier: MPL-2.0
"""Open an ODF file as the storage layout it actually has."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import PackageError

from .flat import FlatXmlStorage
from .package import PackageStorage

if TYPE_CHECKING:
    import os

    from .storage import OdfStorage

ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")
SNIFF_BYTES = 512
BYTE_ORDER_MARK = b"\xef\xbb\xbf"
XML_WHITESPACE = b" \t\r\n"


def open_storage(source: str | os.PathLike[str]) -> OdfStorage:
    """Open an ODF file as a ZIP package or, when it is XML, as a flat document.

    Returns
    -------
    OdfStorage
        The matching storage implementation.

    Raises
    ------
    FileNotFoundError
        The source does not exist.
    PackageError
        The file is neither a ZIP archive nor an XML document, or exceeds a limit.

    """
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as stream:
        head = stream.read(SNIFF_BYTES)
    if head[:4] in ZIP_SIGNATURES:
        return PackageStorage(path)
    if head.removeprefix(BYTE_ORDER_MARK).lstrip(XML_WHITESPACE)[:1] == b"<":
        return FlatXmlStorage(path)
    msg = f"{path.name} is neither a ZIP package nor an XML document"
    raise PackageError(msg)
