# SPDX-License-Identifier: AGPL-3.0-only
"""Family-neutral reading of a document body."""

from odfa11y.odf.names import NS
from odfa11y.odf.storage import Part
lazy from odfa11y.odf.document import OdfDocument


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
