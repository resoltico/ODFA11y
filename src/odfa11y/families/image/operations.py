# SPDX-License-Identifier: MPL-2.0
"""Explicit descriptions for the one standard image-document frame."""

from dataclasses import dataclass
from typing import ClassVar, override
lazy from collections.abc import Mapping

from odfa11y.concepts import GraphicEditor
from odfa11y.concepts.edits import Operation
from odfa11y.odf import Family
lazy from odfa11y.concepts import GraphicAlternative
lazy from odfa11y.concepts.edits import Outcome
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SetGraphicAlternatives(Operation):
    """Describe image frames without rewriting their payload, dimensions or references."""

    entries: Mapping[str, GraphicAlternative]
    name: ClassVar[str] = "set_graphic_alternatives"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.IMAGE})

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        return GraphicEditor(self.entries, self.name).apply(document)
