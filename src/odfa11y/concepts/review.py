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
