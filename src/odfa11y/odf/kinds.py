# SPDX-License-Identifier: AGPL-3.0-only
"""The OpenDocument document kinds: media types, families and body elements.

Pure data about the standard. What a family's documents *mean* belongs to the family's
adapter, never here.
"""

from dataclasses import dataclass
from enum import StrEnum

OASIS_PREFIX = "application/vnd.oasis.opendocument."


class Family(StrEnum):
    """The OpenDocument conformance classes a document can belong to."""

    TEXT = "text"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    DRAWING = "drawing"
    FORMULA = "formula"
    CHART = "chart"
    IMAGE = "image"
    DATABASE = "database"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.TEXT: "A text document expresses prose and its structure.",
            self.SPREADSHEET: "A spreadsheet expresses cells, formulas and tabular relationships.",
            self.PRESENTATION: "A presentation expresses slides and their associated notes.",
            self.DRAWING: "A drawing expresses objects placed on pages.",
            self.FORMULA: "A formula document expresses a mathematical expression.",
            self.CHART: "A chart document expresses data graphically.",
            self.IMAGE: "An image document expresses graphic content.",
            self.DATABASE: (
                "A database document describes forms, reports, queries and data sources."
            ),
        }[self]


@dataclass(frozen=True, slots=True)
class DocumentKind:
    """One media type: its family, whether it is a template, and its body element."""

    media_type: str
    family: Family
    extension: str
    body_element: str | None
    template: bool = False
    deprecated: bool = False

    @property
    def name(self) -> str:
        """A short unique name, for example ``text-template`` or ``base``."""
        if self.family == Family.DRAWING:
            return "drawing-template" if self.template else "drawing"
        short = self.media_type.removeprefix(OASIS_PREFIX).removeprefix("application/vnd.")
        return short.replace(".", "-")


def _kinds() -> tuple[DocumentKind, ...]:
    oasis = OASIS_PREFIX
    return (
        DocumentKind(oasis + "text", Family.TEXT, ".odt", "office:text"),
        DocumentKind(oasis + "text-template", Family.TEXT, ".ott", "office:text", template=True),
        DocumentKind(oasis + "text-master", Family.TEXT, ".odm", "office:text"),
        DocumentKind(
            oasis + "text-master-template", Family.TEXT, ".otm", "office:text", template=True
        ),
        DocumentKind(oasis + "text-web", Family.TEXT, ".oth", "office:text"),
        DocumentKind(oasis + "spreadsheet", Family.SPREADSHEET, ".ods", "office:spreadsheet"),
        DocumentKind(
            oasis + "spreadsheet-template",
            Family.SPREADSHEET,
            ".ots",
            "office:spreadsheet",
            template=True,
        ),
        DocumentKind(oasis + "graphics", Family.DRAWING, ".odg", "office:drawing"),
        DocumentKind(
            oasis + "graphics-template", Family.DRAWING, ".otg", "office:drawing", template=True
        ),
        DocumentKind(oasis + "presentation", Family.PRESENTATION, ".odp", "office:presentation"),
        DocumentKind(
            oasis + "presentation-template",
            Family.PRESENTATION,
            ".otp",
            "office:presentation",
            template=True,
        ),
        DocumentKind(oasis + "chart", Family.CHART, ".odc", "office:chart"),
        DocumentKind(oasis + "chart-template", Family.CHART, ".otc", "office:chart", template=True),
        DocumentKind(oasis + "formula", Family.FORMULA, ".odf", None),
        DocumentKind(oasis + "formula-template", Family.FORMULA, ".otf", None, template=True),
        DocumentKind(oasis + "image", Family.IMAGE, ".odi", "office:image", deprecated=True),
        DocumentKind(
            oasis + "image-template",
            Family.IMAGE,
            ".oti",
            "office:image",
            template=True,
            deprecated=True,
        ),
        DocumentKind(oasis + "base", Family.DATABASE, ".odb", "office:database"),
    )


KINDS: dict[str, DocumentKind] = {kind.media_type: kind for kind in _kinds()}


def kind_for_media_type(media_type: str | None) -> DocumentKind | None:
    """Look up a document kind by its media type.

    Returns
    -------
    DocumentKind | None
        The kind, or None when the media type is not an OpenDocument document type.

    """
    return KINDS.get(media_type or "")
