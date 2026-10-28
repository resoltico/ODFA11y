# SPDX-License-Identifier: MPL-2.0
"""Bound raw inline image extents without interpreting sample bytes as PDF operators."""

from __future__ import annotations

import re

from odfa11y.errors import ToolFailedError

SPACE = rb"\x00\t\n\x0c\r "
NAME_ESCAPE = re.compile(rb"#([0-9a-fA-F]{2})")
INLINE_DATA = re.compile(rb"(?<!/)\bID(?:\r\n|[" + SPACE + rb"])")
INLINE_IMAGE_END = re.compile(rb"[" + SPACE + rb"]+EI(?=[" + SPACE + rb"]|$)")


def inline_image_end(data: bytes, position: int) -> int:
    """Skip raw image samples by their dimensions, never by an EI-looking sample.

    Returns
    -------
    int
        The byte position after the inline image.

    Raises
    ------
    ToolFailedError
        The image is filtered or its sample extent cannot be determined safely.

    """
    start = INLINE_DATA.search(data, position)
    if start is None:
        msg = "Inline image has no data delimiter"
        raise ToolFailedError(msg)
    header = NAME_ESCAPE.sub(
        lambda match: bytes([int(match[1], 16)]), data[position : start.start()]
    )
    if re.search(rb"/(?:F|Filter)\b", header):
        msg = "Filtered inline images are outside the marked-content scanner's scope"
        raise ToolFailedError(msg)
    fields = dict(re.findall(rb"/([A-Za-z]+)\s+([+-]?\d+|/[A-Za-z]+)", header))
    width = int(fields.get(b"W", fields.get(b"Width", b"0")))
    height = int(fields.get(b"H", fields.get(b"Height", b"0")))
    bits = int(fields.get(b"BPC", fields.get(b"BitsPerComponent", b"0")))
    space = fields.get(b"CS", fields.get(b"ColorSpace", b""))
    components = {
        b"/G": 1,
        b"/DeviceGray": 1,
        b"/RGB": 3,
        b"/DeviceRGB": 3,
        b"/CMYK": 4,
        b"/DeviceCMYK": 4,
    }.get(space, 0)
    if re.search(rb"/(?:IM|ImageMask)\s+true\b", header):
        bits, components = 1, 1
    if width <= 0 or height <= 0 or bits not in {1, 2, 4, 8, 16} or not components:
        msg = "Inline image dimensions or color space cannot be inspected"
        raise ToolFailedError(msg)
    end = start.end() + ((width * components * bits + 7) // 8) * height
    marker = INLINE_IMAGE_END.match(data, end)
    if marker is None:
        msg = "Inline image sample length does not match its end delimiter"
        raise ToolFailedError(msg)
    return marker.end()
