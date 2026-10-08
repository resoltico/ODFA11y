# SPDX-License-Identifier: MPL-2.0
"""Synthetic four-color resources with an independent decoded-pixel oracle."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image
from pypdf import PdfReader

from odfa11y.external_tools import run_bounded
from odfa11y.odf import NS, OdfDocument, Part, qn

from .documents import Variant, make_flat

if TYPE_CHECKING:
    from pathlib import Path

COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)] * 4
PIXELS = bytes(channel for color in COLORS for channel in color)
ALT = "<svg:title>Four-color pattern</svg:title><svg:desc>A synthetic four-color image</svg:desc>"


def png_bytes() -> bytes:
    """Encode the independent color oracle as PNG.

    Returns
    -------
    bytes
        A 4x4 RGB PNG.

    """
    data = BytesIO()
    Image.frombytes("RGB", (4, 4), PIXELS).save(data, format="PNG")
    return data.getvalue()


def writer_resource(directory: Path, href: str | None = None) -> Path:
    """Create flat Writer input with an embedded image or one declared render dependency.

    Returns
    -------
    Path
        Schema-defined synthetic document; no URI is fetched.

    """
    image = (
        "<draw:image><office:binary-data>"
        + base64.b64encode(png_bytes()).decode()
        + "</office:binary-data></draw:image>"
        if href is None
        else '<draw:image xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>'
    )
    body = (
        '<office:text><text:h text:outline-level="1">Resource controls</text:h>'
        '<text:p><draw:frame draw:name="Asset" text:anchor-type="paragraph" '
        'svg:width="2cm" svg:height="2cm">' + image + ALT + "</draw:frame></text:p>"
        '<text:p><text:a xlink:href="assets/nested/guide.html" xlink:type="simple" '
        'office:name="Read the guide">Read the guide</text:a></text:p></office:text>'
    )
    path = make_flat(directory, "text", Variant(body=body))
    if href is not None:
        document = OdfDocument.open(path)
        node = document.edit(Part.CONTENT).find(".//draw:image", NS)
        assert node is not None
        node.set(qn("xlink", "href"), href)
        document.save(path)
    return path


def author_package(flat: Path, soffice: str, destination: Path) -> Path:
    """Have current native Writer save a package from the controlled flat input.

    Returns
    -------
    Path
        The actual native package.

    """
    result = run_bounded(
        [
            soffice,
            f"-env:UserInstallation={(destination.parent / 'author-profile').as_uri()}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--convert-to",
            "odt",
            "--outdir",
            str(destination),
            str(flat),
        ],
        timeout=120,
    )
    path = destination / f"{flat.stem}.odt"
    assert result.returncode == 0, result
    assert path.is_file(), result
    OdfDocument.open(path)
    return path


def decoded_images(pdf: Path) -> list[tuple[tuple[int, int], bytes]]:
    """Decode emitted images independently of image count or declared dimensions.

    Returns
    -------
    list[tuple[tuple[int, int], bytes]]
        Dimensions and exact RGB pixels of all exported images, including placeholders.

    """
    found = []
    with PdfReader(pdf) as reader:
        for page in reader.pages:
            for item in page.images:
                with Image.open(BytesIO(item.data)) as image:
                    found.append((image.size, image.convert("RGB").tobytes()))
    return found
