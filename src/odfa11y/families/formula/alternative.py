# SPDX-License-Identifier: MPL-2.0
"""Set a supplied spoken formula alternative without rewriting mathematics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import Family, Part

from .expression import expression, fingerprint

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SetFormulaAlternative(Operation):
    """Apply an explicitly written alternative to the one native MathML expression."""

    text: str
    fingerprint: str | None = None
    name: ClassVar[str] = "set_formula_alternative"
    family: ClassVar[Family | None] = Family.FORMULA

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        root = expression(document)
        if root is None:
            return (
                Outcome(self.name, Status.FAILED, "Formula content must be a native MathML root."),
            )
        if not isinstance(self.text, str) or not self.text.strip():
            return (
                Outcome(
                    self.name, Status.FAILED, "A formula alternative must be a nonblank string."
                ),
            )
        if self.fingerprint is not None and self.fingerprint != fingerprint(root):
            return (
                Outcome(
                    self.name, Status.FAILED, "The mathematical expression changed since review."
                ),
            )
        value = self.text.strip()
        if root.get("alttext") == value:
            return (Outcome(self.name, Status.UNCHANGED, "Formula alternative already matches."),)
        document.edit(Part.CONTENT)
        root.set("alttext", value)
        return (
            Outcome(self.name, Status.APPLIED, "Set the supplied formula alternative.", count=1),
        )
