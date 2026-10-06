# SPDX-License-Identifier: MPL-2.0
"""Links for ODF accessibility workflows."""

from __future__ import annotations

import re

URI_RE = re.compile(
    r"(?P<url>https?://[^\s<>]+)|(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)


def split_trailing_punctuation(raw: str) -> tuple[str, str]:
    """Separate prose punctuation from a visible URL/email conservatively.

    Closing brackets are stripped only when they are unmatched inside the token,
    so URLs that legitimately contain balanced parentheses keep them.

    Returns
    -------
        tuple[str, str]
            The address token and its detached prose punctuation.

    """
    token = raw
    suffix = ""
    while token:
        last = token[-1]
        should_strip = last in ".,;:"
        if last == ")":
            should_strip = token.count(")") > token.count("(")
        elif last == "]":
            should_strip = token.count("]") > token.count("[")
        elif last == "}":
            should_strip = token.count("}") > token.count("{")
        if not should_strip:
            break
        suffix = last + suffix
        token = token[:-1]
    return token, suffix
