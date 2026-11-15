# SPDX-License-Identifier: MPL-2.0
"""Audit a text document's structure: headings, graphics, tables, links, spacers, notes."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Literal

lazy from lxml import etree

from odfa11y.concepts import document_links, link_decision, link_has_description, link_location
from odfa11y.concepts.kinds import LINK_DESCRIPTION
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.contexts import context_location, text_nodes
from odfa11y.families.text.headings.audit import audit_headings, audit_images
from odfa11y.families.text.kinds import LINKIFY_ADDRESSES, REMOVE_SPACERS
from odfa11y.families.text.language.audit import audit_languages
from odfa11y.families.text.links.prose import prose_slots
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.families.text.lists import audit_lists
from odfa11y.families.text.references import audit_references
from odfa11y.families.text.spacing.candidates import spacer_candidates
from odfa11y.families.text.styles.properties import paragraph_style_name
from odfa11y.families.text.tables.audit import audit_tables
from odfa11y.families.text.visibility import audit_visibility
from odfa11y.odf import Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.odf.styles import styles_of
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.families.text.styles.usage import StyleUsage
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class TextStyleMeasurements:
    """Measurements produced by text-styles analysis; None denotes unmeasured data."""

    producer: Literal["text-styles"] = field(default="text-styles", init=False)
    paragraph_styles: Annotated[
        list[StyleUsage] | None, Description("Paragraph style usage and effective spacing.")
    ] = None


def audit_text(document: OdfDocument, report: Report, metadata: DocumentMetadata) -> None:
    """Report the accessibility findings that belong to text documents."""
    content = document.tree(Part.CONTENT)
    audit_visibility(document, report)
    audit_languages(document, report)
    audit_lists(document, report)
    audit_references(document, report)
    audit_headings(content, report, document)
    audit_images(document, report)
    audit_tables(document, report)
    _audit_links(content, report)
    for index, link in enumerate(document_links(document), 1):
        if not link_has_description(link):
            report.raise_(
                rules.LINK003,
                location=link_location(link, index),
                decision=link_decision(document, link, index, LINK_DESCRIPTION),
            )
    _audit_empty_spacers(document, report)
    _audit_blinking(document, report)
    _audit_style_summary(document, report)


def _audit_links(tree: etree._ElementTree, report: Report) -> None:
    """Report URLs and addresses in prose, exactly where linkification would act."""
    counts = {"heading": 0, "paragraph": 0}
    for block in text_nodes(tree, xml_names.TEXT_P, xml_names.TEXT_H):
        kind = "heading" if block.tag == xml_names.TEXT_H else "paragraph"
        counts[kind] += 1
        for owner, attr in prose_slots(block):
            for match in URI_RE.finditer(getattr(owner, attr)):
                token, _suffix = split_trailing_punctuation(match.group(0))
                report.raise_(
                    rules.LINK001,
                    "Visible URL/email address is not represented by a hyperlink element.",
                    location=context_location(block, kind, counts[kind]),
                    details={"text": token},
                    decision=OpenDecision(LINKIFY_ADDRESSES, None, {"enabled": False}),
                )


def _audit_empty_spacers(document: OdfDocument, report: Report) -> None:
    catalog = styles_of(document)
    styles = []
    breaks = 0
    for paragraph in spacer_candidates(document.tree(Part.CONTENT)):
        name = paragraph.get(xml_names.TEXT_STYLE_NAME)
        try:
            breaks += catalog.has_break_semantics(name)
        except DocumentRefusal:
            continue  # the style summary reports these unresolved current-flow styles
        styles.append(name)
    if styles:
        report.raise_(
            rules.LAYOUT001,
            (
                "Empty body paragraphs were found. If they are only visual "
                "spacers, prefer paragraph spacing instead."
            ),
            decision=OpenDecision(REMOVE_SPACERS, None, {"enabled": False}),
            location=Location(Part.CONTENT.value),
            details={
                "count": len(styles),
                "with_break_semantics": breaks,
                "styles": sorted({style or "(none)" for style in styles}),
            },
        )


def _audit_blinking(document: OdfDocument, report: Report) -> None:
    if any(
        select_elements(tree, "//*[@style:text-blinking='true']")
        for tree in document.distinct_trees(Part.CONTENT, Part.STYLES)
    ):
        report.raise_(
            rules.STYLE002,
            "Blinking text styling is present.",
            location=Location(Part.STYLES.value),
        )


def _audit_style_summary(document: OdfDocument, report: Report) -> None:
    rows, problems = _style_rows(document)
    report.measure(TextStyleMeasurements(paragraph_styles=rows))
    if problems:
        report.raise_(
            rules.STYLE001, location=Location(Part.STYLES.value), details={"styles": problems}
        )


def _style_rows(document: OdfDocument) -> tuple[list[StyleUsage], dict[str, str]]:
    counts: Counter[str] = Counter()
    problems = {}
    for node in text_nodes(
        document.tree(Part.CONTENT), xml_names.TEXT_P, xml_names.TEXT_H, main_only=True
    ):
        name = node.get(xml_names.TEXT_STYLE_NAME) or "(none)"
        try:
            paragraph_style_name(node)
        except DocumentRefusal as exc:
            problems[name] = str(exc)
        else:
            counts[name] += 1
    catalog = styles_of(document)
    rows: list[StyleUsage] = []
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        style_name = None if name == "(none)" else name
        try:
            rows.append({
                "style": name,
                "count": count,
                "parent": catalog.parent_name("paragraph", style_name),
                "spacing": catalog.spacing_signature(style_name),
            })
        except DocumentRefusal as exc:
            problems[name] = str(exc)
    return rows, problems
