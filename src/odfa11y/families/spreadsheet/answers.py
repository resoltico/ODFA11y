# SPDX-License-Identifier: MPL-2.0
"""Validated human answers about spreadsheet sheet names."""

from dataclasses import dataclass
from typing import Annotated, ClassVar

from odfa11y.contracts import Constraint, Description, XmlText
from odfa11y.families.spreadsheet.name_rules import invalid_name_reason


@dataclass(frozen=True, slots=True)
class SheetName(Constraint):
    """A native sheet name whose characters are representable in XML."""

    format_name: ClassVar[str] = "odfa11y-sheet-name"

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            return ()
        problem = invalid_name_reason(value)
        return XmlText().problems(value) + ((problem,) if problem else ())

    def schema(self) -> dict[str, object]:
        return {"format": self.format_name}


@dataclass(frozen=True, slots=True)
class SheetNameAnswer:
    """A meaningful sheet name supplied by its reviewer."""

    name: Annotated[str, SheetName(), Description("Name identifying what the sheet contains.")]
