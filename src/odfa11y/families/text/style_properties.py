# SPDX-License-Identifier: MPL-2.0
"""Select styled paragraphs and translate qualified property names."""

from __future__ import annotations

from odfa11y.odf import NS, qn

SPACING_ATTRIBUTES = (
    qn("fo", "margin-top"),
    qn("fo", "margin-bottom"),
    qn("fo", "line-height"),
    qn("fo", "line-height-at-least"),
    qn("style", "contextual-spacing"),
)

BREAK_ATTRIBUTES = (
    qn("fo", "break-before"),
    qn("fo", "break-after"),
    qn("style", "master-page-name"),
)


def display_attr(qname: str) -> str:
    """Render a Clark-notation attribute name with its namespace prefix.

    Returns
    -------
    str
        The prefixed name, or the input when its namespace is unknown.

    """
    for prefix, uri in NS.items():
        marker = f"{{{uri}}}"
        if qname.startswith(marker):
            return f"{prefix}:{qname[len(marker) :]}"
    return qname


def attr_from_display(name: str) -> str:
    """Parse a prefixed attribute name into Clark notation.

    Returns
    -------
    str
        The Clark-notation name, or the input when its prefix is unknown.

    """
    if ":" not in name:
        return name
    prefix, local = name.split(":", 1)
    if prefix not in NS:
        return name
    return qn(prefix, local)
