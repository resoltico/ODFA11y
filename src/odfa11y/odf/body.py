# SPDX-License-Identifier: MPL-2.0
"""Family-neutral reading of a document body."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .namespaces import NS
from .storage import Part

if TYPE_CHECKING:
    from .document import OdfDocument


def body_text_snapshot(document: OdfDocument) -> tuple[str, ...]:
    """Collect the whitespace-normalized text of the whole document body.

    Returns
    -------
    tuple[str, ...]
        One entry holding all body text, or an empty entry when there is no body.

    """
    body = document.tree(Part.CONTENT).getroot().find("office:body", NS)
    if body is None:
        return ("",)
    return (" ".join("".join(body.itertext()).replace("\u00a0", " ").split()),)
