# SPDX-License-Identifier: MPL-2.0
"""Write isolated synthetic ODF probe packages with explicit metadata and local assets."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr
lazy from pathlib import Path

from odfa11y.odf import NS

if TYPE_CHECKING:
    from collections.abc import Mapping

NAMESPACES = " ".join(f"xmlns:{prefix}={quoteattr(uri)}" for prefix, uri in NS.items())


def write_probe_package(
    path: Path,
    media_type: str,
    body: str,
    *,
    automatic_styles: str = "",
    assets: Mapping[str, bytes] | None = None,
    native_content: str | None = None,
) -> Path:
    """Write an ODF 1.4 case without scripts or external fetch dependencies.

    Returns
    -------
    Path
        The closed, local probe input.

    """
    styles = (
        f'<office:document-styles {NAMESPACES} office:version="1.4"><office:styles>'
        '<style:default-style style:family="paragraph"><style:text-properties '
        'fo:language="en" fo:country="US"/></style:default-style>'
        '<style:default-style style:family="table-cell"><style:text-properties '
        'fo:language="en" fo:country="US"/></style:default-style>'
        "</office:styles></office:document-styles>"
    )
    members = {
        "content.xml": native_content
        or (
            f'<office:document-content {NAMESPACES} office:version="1.4">'
            f"<office:automatic-styles>{automatic_styles}</office:automatic-styles>"
            f"<office:body>{body}</office:body></office:document-content>"
        ),
        "styles.xml": styles,
        "meta.xml": (
            f'<office:document-meta {NAMESPACES} office:version="1.4"><office:meta>'
            "<dc:title>ODFA11y capability probe</dc:title><dc:language>en-US</dc:language>"
            "</office:meta></office:document-meta>"
        ),
    }
    resources = {name: value.encode() for name, value in members.items()} | dict(assets or {})
    entries = "".join(
        f'<manifest:file-entry manifest:full-path={quoteattr(name)} manifest:media-type="'
        + ("text/xml" if name.endswith(".xml") else "image/png")
        + '"/>'
        for name in resources
    )
    manifest = (
        f'<manifest:manifest {NAMESPACES} manifest:version="1.4">'
        '<manifest:file-entry manifest:full-path="/" '
        f'manifest:media-type={quoteattr(media_type)} manifest:version="1.4"/>'
        f"{entries}</manifest:manifest>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", media_type, compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/manifest.xml", manifest)
        for name, value in resources.items():
            archive.writestr(name, value, compress_type=zipfile.ZIP_DEFLATED)
    return path
