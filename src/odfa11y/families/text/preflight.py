# SPDX-License-Identifier: MPL-2.0
"""Whole-plan refusals before any supported text operation mutates XML."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import RemediationError
from odfa11y.odf import Part

from .contexts import has_revisions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.odf import OdfDocument


def preflight_text(document: OdfDocument, operations: Sequence[Operation]) -> None:
    """Reject revision editing and unstable ordinal target combinations.

    Raises
    ------
    RemediationError
        A plan includes unsupported effects or unstable ordinal targeting.

    """
    if has_revisions(document.tree(Part.CONTENT)) and any(
        operation.name != "set_metadata"
        or type(operation).__module__ != "odfa11y.remediation.metadata"
        or getattr(operation, "language", None) is not None
        for operation in operations
    ):
        msg = "Tracked revisions permit only title/description metadata edits; nothing was written."
        raise RemediationError(msg)
    names = {operation.name for operation in operations}
    if "set_target_languages" in names and names & {
        "linkify_addresses",
        "mark_table_headers",
        "remove_empty_spacers",
    }:
        message = "Ordinal target languages require a separate reviewed structural plan."
        raise RemediationError(message)
    if names & {"linkify_addresses", "mark_table_headers"}:
        for operation in operations:
            if operation.name == "set_link_descriptions" and any(
                "[id=" not in target for target in getattr(operation, "entries", {})
            ):
                msg = "Ordinal link descriptions require a separate reviewed structural plan."
                raise RemediationError(msg)
