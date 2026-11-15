# SPDX-License-Identifier: MPL-2.0
"""Whole-plan refusals before any supported text operation mutates XML."""

lazy from collections.abc import Sequence

from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.contexts import has_revisions
from odfa11y.odf import Part
lazy from odfa11y.concepts.edits import Operation
lazy from odfa11y.odf import OdfDocument


def preflight_text(document: OdfDocument, operations: Sequence[Operation]) -> None:
    """Reject revision editing and unstable ordinal target combinations.

    Raises
    ------
    DocumentRefusal
        A plan includes unsupported effects or unstable ordinal targeting.

    """
    if has_revisions(document.tree(Part.CONTENT)) and any(
        operation.name != "set_metadata"
        or type(operation).__module__ != "odfa11y.remediate.metadata"
        or getattr(operation, "language", None) is not None
        for operation in operations
    ):
        msg = "Tracked revisions permit only title/description metadata edits; nothing was written."
        raise DocumentRefusal(msg)
    names = {operation.name for operation in operations}
    if "set_target_languages" in names and names & {
        "linkify_addresses",
        "mark_table_headers",
        "remove_empty_spacers",
    }:
        message = "Ordinal target languages require a separate reviewed structural plan."
        raise DocumentRefusal(message)
    if names & {"linkify_addresses", "mark_table_headers"}:
        for operation in operations:
            if operation.name == "set_link_descriptions" and any(
                "[id=" not in target for target in getattr(operation, "entries", {})
            ):
                msg = "Ordinal link descriptions require a separate reviewed structural plan."
                raise DocumentRefusal(msg)
