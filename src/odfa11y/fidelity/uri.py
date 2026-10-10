# SPDX-License-Identifier: MPL-2.0
"""Resolve supported PDF URI actions without accessing their destinations."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from pypdf.errors import PdfReadError
from pypdf.generic import DictionaryObject, TextStringObject

from odfa11y.pdf_consumption import resolve

_UNRESERVED_SUBDELIMS = r"(?:[A-Za-z0-9._~!$&'()*+,;=-]|%[0-9A-Fa-f]{2})"
_PCHAR = rf"(?:{_UNRESERVED_SUBDELIMS}|[:@])"
_PATH = re.compile(rf"(?:{_PCHAR}|/)*")
_QUERY_FRAGMENT = re.compile(rf"(?:{_PCHAR}|[/?])*")
_AUTHORITY = re.compile(
    rf"(?:(?:{_UNRESERVED_SUBDELIMS}|:)*@)?"
    rf"(?:{_UNRESERVED_SUBDELIMS}*|\[[A-Za-z0-9._~!$&'()*+,;=:-]+\])(?::[0-9]*)?"
)
_RELATIVE_BASE_SCHEMES = {"http", "https", "ftp", "file"}


def _uri(value: object, field: str) -> str:
    value = resolve(value)
    if not isinstance(value, TextStringObject):
        msg = f"Expected a valid PDF {field} URI string"
        raise PdfReadError(msg)
    if any(ord(character) <= ord(" ") for character in value):
        msg = f"Malformed PDF {field} URI characters"
        raise PdfReadError(msg)
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        msg = f"Malformed PDF {field} URI"
        raise PdfReadError(msg) from exc
    if not (
        _AUTHORITY.fullmatch(parts.netloc)
        and _PATH.fullmatch(parts.path)
        and _QUERY_FRAGMENT.fullmatch(parts.query)
        and _QUERY_FRAGMENT.fullmatch(parts.fragment)
    ):
        msg = f"Malformed PDF {field} URI components"
        raise PdfReadError(msg)
    if not parts.scheme and ":" in parts.path.split("/", 1)[0]:
        msg = f"Malformed PDF {field} relative URI"
        raise PdfReadError(msg)
    return value


def uri_base(catalog: DictionaryObject) -> str | None:
    """Read an explicit catalog URI Base, resolving indirect dictionaries and strings.

    Returns
    -------
    str or None
        The syntactically valid Base, or None if absent.

    Raises
    ------
    PdfReadError
        The catalog URI dictionary or Base is malformed.

    """
    settings = resolve(catalog.get("/URI"))
    if settings is None:
        return None
    if not isinstance(settings, DictionaryObject):
        msg = "Expected a PDF catalog URI dictionary"
        raise PdfReadError(msg)
    return _uri(settings["/Base"], "Base") if "/Base" in settings else None


def effective_uri(value: object, base: str | None) -> str:
    """Resolve a relative URI against an established hierarchical catalog Base.

    Returns
    -------
    str
        An absolute target, preserving query/fragment delimiters and encoded characters.

    Raises
    ------
    PdfReadError
        The action URI is malformed or its relative context is unsupported.

    """
    uri = _uri(value, "action")
    if urlsplit(uri).scheme:
        return uri
    parts = urlsplit(base or "")
    if parts.scheme not in _RELATIVE_BASE_SCHEMES or not (
        parts.netloc or (parts.scheme == "file" and parts.path.startswith("/"))
    ):
        msg = "Relative PDF URI requires an explicit absolute http, https, ftp or file Base"
        raise PdfReadError(msg)
    reference = urlsplit(uri)
    query_present = "?" in uri.split("#", 1)[0]
    authority = reference.netloc if uri.startswith("//") else parts.netloc
    if uri.startswith("//"):
        path = _remove_dot_segments(reference.path)
        query = reference.query
    elif not reference.path:
        path = parts.path
        query = reference.query if query_present else parts.query
        query_present = query_present or "?" in (base or "").split("#", 1)[0]
    else:
        merged = reference.path
        if not merged.startswith("/"):
            directory = parts.path.rsplit("/", 1)[0] if "/" in parts.path else ""
            merged = directory + "/" + merged
        path = _remove_dot_segments(merged)
        query = reference.query
    target = urlunsplit((parts.scheme, authority, path, query, reference.fragment))
    if query_present and not query:
        body, marker, fragment = target.partition("#")
        target = body + "?" + (marker + fragment if marker else "")
    if "#" in uri and not reference.fragment:
        target += "#"
    return target


def _remove_dot_segments(path: str) -> str:
    # RFC 3986 section 5.2.4. Preserve repeated slashes and percent-encoded dots.
    output = ""
    while path:
        if path.startswith(("../", "./")):
            path = path.partition("/")[2]
        elif path.startswith("/./") or path == "/.":
            path = "/" + path[3:]
        elif path.startswith("/../") or path == "/..":
            path = "/" + path[4:]
            output = output.rsplit("/", 1)[0]
        elif path in {".", ".."}:
            path = ""
        else:
            end = path.find("/", 1 if path.startswith("/") else 0)
            end = len(path) if end < 0 else end
            output += path[:end]
            path = path[end:]
    return output
