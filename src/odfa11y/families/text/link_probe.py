# SPDX-License-Identifier: MPL-2.0
"""A minimal text document with one hyperlink, for probing what the PDF export does with links."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

MIMETYPE = "application/vnd.oasis.opendocument.text"
MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
    'manifest:version="1.3">'
    f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{MIMETYPE}"/>'
    '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
    "</manifest:manifest>"
)
CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.3">'
    "<office:body><office:text><text:p>Read the "
    '<text:a xlink:type="simple" xlink:href="https://example.com/">example link</text:a>.'
    "</text:p></office:text></office:body></office:document-content>"
)


def write_link_probe(path: Path) -> None:
    """Write a one-paragraph text document with a single hyperlink, to ``path``."""
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
        package.writestr("META-INF/manifest.xml", MANIFEST, compress_type=zipfile.ZIP_DEFLATED)
        package.writestr("content.xml", CONTENT, compress_type=zipfile.ZIP_DEFLATED)
