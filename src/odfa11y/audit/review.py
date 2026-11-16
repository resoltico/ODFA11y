# SPDX-License-Identifier: MPL-2.0
"""Establish which human-review topics are present in an audited document."""

from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.odf import OdfDocument, Part, names


def review_topics(document: OdfDocument) -> tuple[Topic, ...]:
    """Select topics from actual authored elements, rather than family membership alone."""
    content = document.tree(Part.CONTENT)
    tags = {node.tag for node in content.iter()}
    text = bool(tags & {names.TEXT_P, names.TEXT_H})
    graphics = bool(tags & {names.DRAW_IMAGE, names.DRAW_OBJECT, names.DRAW_FRAME})
    sheets = names.TABLE_TABLE in tags
    pages = names.DRAW_PAGE in tags
    present = {
        Topic.HEADINGS: names.TEXT_H in tags,
        Topic.ALT_TEXT: graphics,
        Topic.IMAGE_MEANING: graphics,
        Topic.TABLE_HEADERS: sheets,
        Topic.HEADER_CELLS: sheets,
        Topic.LABELS_AND_RANGES: sheets,
        Topic.SHEET_NAMES: sheets,
        Topic.LISTS: names.TEXT_LIST in tags,
        Topic.LINK_PURPOSE: bool(tags & {names.TEXT_A, names.DRAW_A}),
        Topic.HIDDEN_CONTENT: bool(
            tags
            & {
                names.TEXT_HIDDEN_TEXT,
                names.TEXT_HIDDEN_PARAGRAPH,
                names.TEXT_TRACKED_CHANGES,
            }
        ),
        Topic.LANGUAGE: text,
        Topic.READING_ORDER: text or graphics or pages,
        Topic.LAYOUT: text or graphics or pages or sheets,
        Topic.COLOUR: graphics,
        Topic.COLOUR_AND_LAYOUT: graphics or pages,
        Topic.CHART_MEANING: names.CHART_CHART in tags,
        Topic.MATHEMATICS: names.MATH_MATH in tags,
        Topic.PAGE_TITLES: pages,
        Topic.SLIDES_AND_NOTES: pages,
    }
    return tuple(topic for topic, exists in present.items() if exists)
