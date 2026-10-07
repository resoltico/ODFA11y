# SPDX-License-Identifier: MPL-2.0
"""Explicit page and graphic decisions for drawing documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation
from odfa11y.content import SHAPE_TAGS, GraphicEditor, PageEditor
from odfa11y.odf import Family

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.adapter import Outcome
    from odfa11y.content import GraphicDescription, PageDecision
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SetPageSemantics(Operation):
    """Apply reviewed descriptions and complete navigation without changing page contents."""

    entries: Mapping[str, PageDecision]
    name: ClassVar[str] = "set_page_semantics"
    family: ClassVar[Family | None] = Family.GRAPHICS

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return PageEditor(self.entries, self.name).apply(document)


@dataclass(frozen=True, slots=True)
class SetGraphicDescriptions(Operation):
    """Describe frames and vector shapes without changing their text or geometry."""

    entries: Mapping[str, GraphicDescription]
    name: ClassVar[str] = "set_graphic_descriptions"
    family: ClassVar[Family | None] = Family.GRAPHICS

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return GraphicEditor(self.entries, self.name, SHAPE_TAGS).apply(document)
