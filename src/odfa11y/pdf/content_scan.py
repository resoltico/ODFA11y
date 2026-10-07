# SPDX-License-Identifier: MPL-2.0
"""Scan a page content stream for marked-content identifiers and unmarked text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odfa11y.errors import ToolFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

_SPACE = rb"\x00\t\n\x0c\r "
_REGULAR = rb"[^" + _SPACE + rb"()<>\[\]{}/%]"
_TOKEN = re.compile(
    rb"[" + _SPACE + rb"]+|%[^\r\n]*"
    rb"|(?P<string>\()"
    rb"|(?P<dict_open><<)|(?P<dict_close>>>)"
    rb"|(?P<hex><[^>]*>?)"
    rb"|(?P<name>/" + _REGULAR + rb"*)"
    rb"|(?P<word>" + _REGULAR + rb"+)"
    rb"|(?P<delimiter>[\[\]{})>])"
)
_NAME_ESCAPE = re.compile(rb"#([0-9a-fA-F]{2})")
_STRING_EDGE = re.compile(rb"[()\\]")
_INLINE_DATA = re.compile(rb"(?<!/)\bID(?:\r\n|[" + _SPACE + rb"])")
_INLINE_IMAGE_END = re.compile(rb"[" + _SPACE + rb"]+EI(?=[" + _SPACE + rb"]|$)")
_TEXT_SHOWING = {b"Tj", b"TJ", b"'", b'"'}
_ARTIFACT = ("name", "/Artifact")
_NO_OPERAND = ("", None)
_NUMBER_START = b"+-.0123456789"
PROPERTY_LIST = 2  # BDC takes a tag and its properties

Operand = tuple[str, int | str | None]


@dataclass(slots=True)
class ContentScan:
    """What a content stream declares: its MCIDs and its text shown outside tagged content."""

    mcids: set[int] = field(default_factory=set)
    unmarked_text_operations: int = 0


@dataclass(slots=True)
class _Scanner:
    properties: Callable[[str], int | None]
    scan: ContentScan = field(default_factory=ContentScan)
    sequences: list[bool] = field(default_factory=list)  # True: tags real content or is artifact
    covered: int = 0
    operands: list[Operand] = field(default_factory=list)
    dict_depth: int = 0
    dict_key: str = ""
    dict_mcid: int | None = None

    def operand(self, kind: str, value: int | str | None = None) -> None:
        self.operands.append((kind, value))
        del self.operands[:-2]  # an operator reads at most its last two operands

    def inside_dictionary(self, kind: str, text: str) -> None:
        if kind == "name":
            self.dict_key = text
        elif kind == "word" and self.dict_depth == 1 and self.dict_key == "/MCID":
            self.dict_mcid = int(text) if text.lstrip("+").isdigit() else None
            self.dict_key = ""

    def token(self, kind: str, text: bytes) -> None:
        if kind == "dict_open":
            if not self.dict_depth:
                self.dict_mcid, self.dict_key = None, ""
            self.dict_depth += 1
        elif kind == "dict_close":
            self.dict_depth = max(self.dict_depth - 1, 0)
            if not self.dict_depth:
                self.operand("dict", self.dict_mcid)
        elif self.dict_depth:
            decoded = _NAME_ESCAPE.sub(lambda match: bytes([int(match[1], 16)]), text)
            self.inside_dictionary(kind, decoded.decode("latin-1"))
        elif kind == "name":
            decoded = _NAME_ESCAPE.sub(lambda match: bytes([int(match[1], 16)]), text)
            self.operand("name", decoded.decode("latin-1"))
        elif kind == "word" and text[0] not in _NUMBER_START:
            self.operator(text)

    def operator(self, word: bytes) -> None:
        if word == b"BDC":
            self._begin(list(self.operands) if len(self.operands) == PROPERTY_LIST else [])
        elif word == b"BMC":
            self._begin(self.operands[-1:])
        elif word == b"EMC":
            if self.sequences:
                self.covered -= self.sequences.pop()
        elif word in _TEXT_SHOWING and not self.covered:
            self.scan.unmarked_text_operations += 1
        self.operands.clear()

    def _begin(self, operands: list[Operand]) -> None:
        tag = operands[0] if operands else _NO_OPERAND
        mcid = None
        if len(operands) == PROPERTY_LIST:
            kind, value = operands[1]
            if kind == "dict":
                mcid = value
            elif kind == "name":
                mcid = self.properties(str(value))
        if isinstance(mcid, int):
            self.scan.mcids.add(mcid)
        marks = isinstance(mcid, int) or tag == _ARTIFACT
        self.sequences.append(marks)
        self.covered += marks


def scan_content(data: bytes, properties: Callable[[str], int | None]) -> ContentScan:
    """Find the MCIDs of a content stream and count text shown outside tagged content.

    A text-showing operator is unmarked when no enclosing marked-content sequence carries an
    MCID or is an ``/Artifact``. Work is linear in the stream: one pass, with strings and
    inline-image data skipped rather than re-scanned. Form XObjects are not entered.

    Parameters
    ----------
    data
        The decoded content stream.
    properties
        Resolves a ``/Properties`` resource name to the MCID of its property list, if any.

    Returns
    -------
    ContentScan
        The MCIDs found and the count of unmarked text-showing operations.

    """
    scanner = _Scanner(properties)
    position = 0
    while match := _TOKEN.match(data, position):
        position = match.end()
        kind = match.lastgroup
        if kind == "string":
            position = _end_of_string(data, position)
        elif match.group() == b"BI":
            position = _inline_image_end(data, position)
            scanner.operands.clear()
        elif kind is not None:
            scanner.token(kind, match.group())
    return scanner.scan


def _end_of_string(data: bytes, position: int) -> int:
    depth = 1
    while depth:
        edge = _STRING_EDGE.search(data, position)
        if edge is None:
            return len(data)
        position = edge.end()
        character = edge.group()
        if character == b"\\":
            position += 1
        else:
            depth += 1 if character == b"(" else -1
    return position


def _inline_image_end(data: bytes, position: int) -> int:
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
    start = _INLINE_DATA.search(data, position)
    if start is None:
        msg = "Inline image has no data delimiter"
        raise ToolFailedError(msg)
    header = _NAME_ESCAPE.sub(
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
    marker = _INLINE_IMAGE_END.match(data, end)
    if marker is None:
        msg = "Inline image sample length does not match its end delimiter"
        raise ToolFailedError(msg)
    return marker.end()
