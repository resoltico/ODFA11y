# SPDX-License-Identifier: MPL-2.0
"""Explicit graphic descriptions for the spreadsheet family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation
from odfa11y.content import GraphicEditor
from odfa11y.odf import Family

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.adapter import Outcome
    from odfa11y.content import GraphicDescription
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SetGraphicDescriptions(Operation):
    """Apply reviewed descriptions without changing visible text or graphic payloads."""

    entries: Mapping[str, GraphicDescription]
    name: ClassVar[str] = "set_graphic_descriptions"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return GraphicEditor(self.entries, self.name).apply(document)
