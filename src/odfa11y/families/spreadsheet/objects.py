# SPDX-License-Identifier: MPL-2.0
"""Explicit graphic descriptions for the spreadsheet family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation
from odfa11y.content import SHAPE_TAGS, GraphicEditor, LinkEditor
from odfa11y.odf import Family

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.adapter import Outcome
    from odfa11y.content import GraphicAlternative, LinkDescription
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SetGraphicAlternatives(Operation):
    """Apply reviewed descriptions without changing visible text or graphic payloads."""

    entries: Mapping[str, GraphicAlternative]
    name: ClassVar[str] = "set_graphic_alternatives"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return GraphicEditor(self.entries, self.name, SHAPE_TAGS).apply(document)


@dataclass(frozen=True, slots=True)
class SetLinkDescriptions(Operation):
    """Set reviewed native link descriptions without changing targets or visible labels."""

    entries: Mapping[str, LinkDescription]
    name: ClassVar[str] = "set_link_descriptions"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return LinkEditor(self.entries, self.name).apply(document)
