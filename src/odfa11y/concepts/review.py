# SPDX-License-Identifier: MPL-2.0
"""concepts review vocabulary."""

from enum import StrEnum


class ReviewTopic(StrEnum):
    """Shared human-review subjects; each family supplies its own guidance."""

    ALT_TEXT = "alt-text"
    CHART_MEANING = "chart-meaning"
    COLOUR = "colour"
    COLOUR_AND_LAYOUT = "colour-and-layout"
    DATABASE_MEANING = "database-meaning"
    EXPORT_BOUNDARY = "export-boundary"
    HEADER_CELLS = "header-cells"
    HEADINGS = "headings"
    HIDDEN_CONTENT = "hidden-content"
    IMAGE_MEANING = "image-meaning"
    LABELS_AND_RANGES = "labels-and-ranges"
    LANGUAGE = "language"
    LAYERS_AND_ANNOTATIONS = "layers-and-annotations"
    LAYOUT = "layout"
    LINK_PURPOSE = "link-purpose"
    LISTS = "lists"
    MATHEMATICS = "mathematics"
    PAGE_TITLES = "page-titles"
    PRIVACY_AND_EXECUTION = "privacy-and-execution"
    READING_ORDER = "reading-order"
    SHEET_NAMES = "sheet-names"
    SLIDES_AND_NOTES = "slides-and-notes"
    SOURCE_ASSURANCE = "source-assurance"
    SOURCE_BOUNDARY = "source-boundary"
    TABLE_HEADERS = "table-headers"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.ALT_TEXT: "Review whether graphic alternatives convey the intended meaning.",
            self.CHART_MEANING: (
                "Review whether chart descriptions explain the data and its significance."
            ),
            self.COLOUR: "Review whether meaning depends solely on colour.",
            self.COLOUR_AND_LAYOUT: (
                "Review whether colour and placement communicate meaning accessibly."
            ),
            self.DATABASE_MEANING: (
                "Review whether database object descriptions explain their purpose."
            ),
            self.EXPORT_BOUNDARY: "Review the limits of native export assurance.",
            self.HEADER_CELLS: (
                "Review whether header cells identify the intended data relationships."
            ),
            self.HEADINGS: "Review whether headings express the intended outline.",
            self.HIDDEN_CONTENT: (
                "Review whether hidden content belongs in the accessible publication."
            ),
            self.IMAGE_MEANING: "Review whether image descriptions explain their relevant content.",
            self.LABELS_AND_RANGES: (
                "Review whether sheet labels and ranges express the intended data relationships."
            ),
            self.LANGUAGE: "Review whether declared languages match the actual content.",
            self.LAYERS_AND_ANNOTATIONS: (
                "Review whether layers and annotations preserve meaningful content."
            ),
            self.LAYOUT: "Review whether placement and spacing preserve the intended reading flow.",
            self.LINK_PURPOSE: (
                "Review whether link descriptions explain each destination or action."
            ),
            self.LISTS: "Review whether list structure expresses the intended grouping.",
            self.MATHEMATICS: (
                "Review whether spoken alternatives convey the mathematical expression."
            ),
            self.PAGE_TITLES: "Review whether page titles identify their purpose.",
            self.PRIVACY_AND_EXECUTION: (
                "Review whether the publication contains private data or active content."
            ),
            self.READING_ORDER: "Review whether the content follows the intended reading sequence.",
            self.SHEET_NAMES: "Review whether worksheet names clearly identify their content.",
            self.SLIDES_AND_NOTES: (
                "Review whether slides and notes communicate their intended content."
            ),
            self.SOURCE_ASSURANCE: "Review the limits of source-only accessibility assurance.",
            self.SOURCE_BOUNDARY: "Review the limits of the source inspection contract.",
            self.TABLE_HEADERS: (
                "Review whether table headers identify the intended row and column relationships."
            ),
        }[self]
