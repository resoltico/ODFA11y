# SPDX-License-Identifier: MPL-2.0
"""Scan a page content stream for marked-content identifiers and unmarked text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .inline_image import inline_image_end

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
_TEXT_SHOWING = {b"Tj", b"TJ", b"'", b'"'}
_ARTIFACT = ("name", "/Artifact")
_NO_OPERAND = ("", None)
_NUMBER_START = b"+-.0123456789"
_NUMBER = re.compile(rb"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_PATH_ARGUMENTS = {b"m": 2, b"re": 4, b"l": 2, b"c": 6, b"v": 4, b"y": 4}
MAX_OPERANDS = 6
ARTIFACT_FLAG = 1
GRAPHICS_FLAG = 2
PROPERTY_LIST = 2  # BDC takes a tag and its properties

Operand = tuple[str, int | str | None]


@dataclass(slots=True)
class ContentScan:
    """What a content stream declares: its MCIDs and its text shown outside tagged content."""

    mcids: set[int] = field(default_factory=set)
    unmarked_text_operations: int = 0
    graphical_mcids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class _Scanner:
    properties: Callable[[str], int | None]
    image: Callable[[str], bool] | None = None
    scan: ContentScan = field(default_factory=ContentScan)
    sequences: list[int | None] = field(default_factory=list)
    flags: bytearray = field(default_factory=bytearray)
    artifacts: int = 0
    path_started: bool = False
    path_drawable: bool = False
    covered: int = 0
    operands: list[Operand] = field(default_factory=list)
    dict_depth: int = 0
    array_depth: int = 0
    dict_key: str = ""
    dict_mcid: int | None = None

    def operand(self, kind: str, value: int | str | None = None) -> None:
        self.operands.append((kind, value))
        del self.operands[:-MAX_OPERANDS]

    def inside_dictionary(self, kind: str, text: str) -> None:
        if kind == "name":
            self.dict_key = text
        elif kind == "word" and self.dict_depth == 1 and self.dict_key == "/MCID":
            self.dict_mcid = int(text) if text.lstrip("+").isdigit() else None
            self.dict_key = ""

    def token(self, kind: str, text: bytes) -> None:
        if (self.array_depth or kind == "delimiter") and self._array(kind, text):
            return
        if kind == "dict_open":
            if not self.dict_depth:
                self.dict_mcid, self.dict_key = None, ""
            self.dict_depth += 1
        elif kind == "dict_close":
            self.dict_depth = max(self.dict_depth - 1, 0)
            if not self.dict_depth:
                self.operand("dict", self.dict_mcid)
        elif self.dict_depth:
            self.inside_dictionary(
                kind, _decode_name(text) if kind == "name" else text.decode("latin-1")
            )
        elif kind == "name":
            self.operand("name", _decode_name(text))
        elif kind == "word":
            self._word(text)

    def _word(self, text: bytes) -> None:
        if text[0] not in _NUMBER_START:
            self.operator(text)
        else:
            self.operand("number" if _NUMBER.fullmatch(text) else "invalid")

    def _array(self, kind: str, text: bytes) -> bool:
        if kind == "delimiter" and text == b"[":
            if not self.dict_depth and not self.array_depth:
                self.operand("array")
            self.array_depth += 1
            self.dict_key = ""
            return True
        if self.array_depth:
            if kind == "delimiter" and text == b"]":
                self.array_depth -= 1
            return True
        return False

    def operator(self, word: bytes) -> None:
        if word == b"BDC":
            self._begin(list(self.operands) if len(self.operands) == PROPERTY_LIST else [])
        elif word == b"BMC":
            self._begin(self.operands[-1:])
        elif word == b"EMC":
            self._end()
        elif word in _TEXT_SHOWING and not self.covered:
            self.scan.unmarked_text_operations += 1
        elif word == b"Do":
            kind, name = self.operands[-1] if self.operands else _NO_OPERAND
            if kind == "name" and self.image is not None and self.image(str(name)):
                self.paint()
        else:
            self._path(word)
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
        identity = mcid if type(mcid) is int and mcid >= 0 else None
        if identity is not None:
            self.scan.mcids.add(identity)
        artifact = tag == _ARTIFACT
        self.sequences.append(identity)
        self.flags.append(ARTIFACT_FLAG if artifact else 0)
        self.covered += identity is not None or artifact
        self.artifacts += artifact

    def paint(self) -> None:
        if self.sequences and not self.artifacts:
            self.flags[-1] |= GRAPHICS_FLAG

    def _end(self) -> None:
        if not self.sequences:
            return
        identity = self.sequences.pop()
        flags = self.flags.pop()
        artifact = bool(flags & ARTIFACT_FLAG)
        self.covered -= identity is not None or artifact
        self.artifacts -= artifact
        if flags & GRAPHICS_FLAG:
            if identity is not None:
                self.scan.graphical_mcids.add(identity)
            if self.sequences and not self.artifacts:
                self.flags[-1] |= GRAPHICS_FLAG

    def _path(self, word: bytes) -> None:
        expected = _PATH_ARGUMENTS.get(word)
        if expected is not None and (
            len(self.operands) != expected or any(kind != "number" for kind, _ in self.operands)
        ):
            return
        if word == b"m":
            self.path_started = True
        elif word == b"re":
            self.path_started = self.path_drawable = True
        elif word in {b"l", b"c", b"v", b"y"} and self.path_started:
            self.path_drawable = True
        elif word in {b"f", b"F", b"f*", b"S", b"s", b"B", b"B*", b"b", b"b*", b"n"}:
            if word != b"n" and self.path_drawable:
                self.paint()
            self.path_started = self.path_drawable = False


def scan_content(
    data: bytes, properties: Callable[[str], int | None], image: Callable[[str], bool] | None = None
) -> ContentScan:
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
    image
        Resolves an invoked resource name to a validated image resource. Forms are excluded.

    Returns
    -------
    ContentScan
        The MCIDs found and the count of unmarked text-showing operations.

    """
    scanner = _Scanner(properties, image)
    position = 0
    while match := _TOKEN.match(data, position):
        position = match.end()
        kind = match.lastgroup
        if kind == "string":
            position = _end_of_string(data, position)
            if not scanner.dict_depth and not scanner.array_depth:
                scanner.operand("string")
        elif match.group() == b"BI":
            position = inline_image_end(data, position)
            scanner.paint()
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


def _decode_name(text: bytes) -> str:
    if b"#" in text:
        text = _NAME_ESCAPE.sub(lambda match: bytes([int(match[1], 16)]), text)
    return text.decode("latin-1")
