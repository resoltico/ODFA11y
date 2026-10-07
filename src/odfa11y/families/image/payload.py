# SPDX-License-Identifier: MPL-2.0
"""Verify locally supplied image data without fetching resources or decoding full pixels."""

from __future__ import annotations

import base64
import binascii
import io
import re
import warnings
from typing import TYPE_CHECKING

from lxml import etree
from PIL import Image, UnidentifiedImageError

from odfa11y.content import local_resource_path
from odfa11y.odf import NS, qn
from odfa11y.safe_xml import parse_secure

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)


def inspect_payload(document: OdfDocument, image: etree._Element) -> tuple[str | None, bool]:
    """Verify available local/embedded image syntax; unavailable data is reported elsewhere.

    Returns
    -------
    tuple[str | None, bool]
        A malformed/uninspectable problem and whether SVG declarations need native review.

    """
    try:
        data = _data(document, image)
        return _verify(data) if data is not None else (None, False)
    except (
        binascii.Error,
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        etree.XMLSyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return "Image payload is malformed or exceeds the image inspector's safe limits.", False


def _data(document: OdfDocument, image: etree._Element) -> bytes | None:
    embedded = image.find("office:binary-data", NS)
    if embedded is not None:
        return base64.b64decode("".join("".join(embedded.itertext()).split()), validate=True)
    name = local_resource_path(image.get(qn("xlink", "href"), ""))
    return document.storage.read(name) if name is not None and document.storage.has(name) else None


def _verify(data: bytes) -> tuple[str | None, bool]:
    if data.lstrip().startswith((b"<", b"\xef\xbb\xbf")):
        root = parse_secure(data)
        if root.tag != f"{{{SVG_NAMESPACE}}}svg":
            return "XML image payload is not an SVG root.", False
        info = root.getroottree().docinfo
        if (
            info.system_url
            or info.public_id
            or any(node.tag is etree.Entity for node in root.iter())
        ):
            return "SVG payload depends on unresolved XML declarations.", False
        return None, _requires_review(root)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as graphic:
            graphic.verify()
    return None, False


def _requires_review(root: etree._Element) -> bool:
    if root.getroottree().xpath("//processing-instruction('xml-stylesheet')"):
        return True
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag in {f"{{{SVG_NAMESPACE}}}script", f"{{{SVG_NAMESPACE}}}foreignObject"}:
            return True
        for name, value in node.attrib.items():
            local = etree.QName(name).localname
            if local.startswith("on") or (
                local in {"href", "src"} and value and not value.startswith("#")
            ):
                return True
            if _external_css(value):
                return True
        if node.tag == f"{{{SVG_NAMESPACE}}}style":
            css = "".join(node.itertext()).lower()
            if _external_css(css) or "@import" in css:
                return True
    return False


def _external_css(value: str) -> bool:
    matches = list(CSS_URL.finditer(value))
    return any(not match[2].strip().startswith("#") for match in matches) or (
        "url(" in value.lower() and not matches
    )
