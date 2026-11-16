# SPDX-License-Identifier: AGPL-3.0-only
"""Decide which document uses declared protection and package names permit."""

from enum import StrEnum

from odfa11y.errors import PackageError
lazy from odfa11y.odf.encryption import PackageProtection


class Use(StrEnum):
    """The guarded purpose for which a document is accessed."""

    AUDIT = "audit"
    PLAN = "plan"
    REMEDIATE = "remediate"
    EXPORT = "export"
    STYLE = "style"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.AUDIT: "Inspect the source without changing it.",
            self.PLAN: "Prepare source-bound questions for human decisions.",
            self.REMEDIATE: "Apply explicitly reviewed source edits.",
            self.EXPORT: (
                "Send a source with established rendering dependencies to its native exporter."
            ),
            self.STYLE: "Inspect style declarations and usage without changing the source.",
        }[self]


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
