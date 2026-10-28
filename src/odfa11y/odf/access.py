# SPDX-License-Identifier: MPL-2.0
"""Decide which document uses declared protection and package names permit."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from odfa11y.errors import PackageError

if TYPE_CHECKING:
    from .protection import PackageProtection


class Use(StrEnum):
    """The guarded purpose for which a document is accessed."""

    AUDIT = "audit"
    PLAN = "plan"
    REMEDIATE = "remediate"
    EXPORT = "export"
    STYLE = "style"


USE_LABELS = {
    Use.AUDIT: "source inspection",
    Use.PLAN: "plan preparation",
    Use.REMEDIATE: "remediation",
    Use.EXPORT: "native export",
    Use.STYLE: "style inspection",
}


def require_access(protection: PackageProtection, use: Use) -> None:
    """Refuse unusable package views and edits of signature-bearing sources.

    Raises
    ------
    PackageError
        Declarations, ambiguous/unsafe names or signatures prevent the selected use.

    """
    if protection.inspection_blocked or (use == Use.REMEDIATE and protection.signatures):
        msg = (
            "Protected, encrypted, ambiguous, unsafe or malformed package cannot establish "
            f"{USE_LABELS[use]}."
        )
        raise PackageError(msg)
