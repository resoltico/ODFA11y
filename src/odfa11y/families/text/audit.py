# SPDX-License-Identifier: MPL-2.0
"""Audit a text document's structure: headings, graphics, tables, links, spacers, notes."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from odfa11y.content import (
    document_links,
    link_decision,
    link_has_description,
    link_location,
)
from odfa11y.decisions import OpenDecision
from odfa11y.errors import RemediationError
from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import FactKeys, Location, rules

from .contexts import context_location, has_revisions, text_nodes
from .decisions import LINKIFY_ADDRESSES, REMOVE_SPACERS
from .language.audit import audit_languages
from .links import URI_RE, split_trailing_punctuation
from .lists import audit_lists
from .prose import prose_slots
from .references import audit_references
from .semantics import audit_headings, audit_images, audit_tables
from .spacers import spacer_candidates
from .style_properties import paragraph_style_name
from .styles import catalog_of

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.adapter import StyleUsage
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_text(document: OdfDocument, report: Report) -> None:
    """Report the accessibility findings that belong to text documents."""
    content = document.tree(Part.CONTENT)
    if has_revisions(content):
        report.add(rules.REVISION001)
    if select_elements(
        content,
        (
            "//text:hidden-text | //text:conditional-text | //text:hidden-paragraph | "
            "//text:section[@text:condition or @text:display='none' or @text:display='condition']"
        ),
    ):
        report.add(rules.HIDDEN001)
    audit_languages(document, report)
    audit_lists(document, report)
    audit_references(document, report)
    audit_headings(content, report, document)
    audit_images(document, report)
    audit_tables(content, report, document)
    _audit_links(content, report)
    for index, link in enumerate(document_links(document), 1):
        if not link_has_description(link):
            report.add(
                rules.LINK003,
                location=link_location(link, index),
            )
            report.add_decision(link_decision(document, link, index, rules.LINK003.id))
    _audit_empty_spacers(document, report)
    _audit_blinking(document, report)
    _audit_style_summary(document, report)

    for kind, rule in [(LINKIFY_ADDRESSES, rules.LINK001), (REMOVE_SPACERS, rules.LAYOUT001)]:
        if any(finding.rule_id == rule.id for finding in report.findings):
            report.add_decision(OpenDecision(kind, None, None, {"enabled": False}, (rule.id,)))


def _audit_links(tree: etree._ElementTree, report: Report) -> None:
    """Report URLs and addresses in prose, exactly where linkification would act."""
    counts = {"heading": 0, "paragraph": 0}
    for block in text_nodes(tree, qn("text", "p"), qn("text", "h")):
        kind = "heading" if block.tag == qn("text", "h") else "paragraph"
        counts[kind] += 1
        for owner, attr in prose_slots(block):
            for match in URI_RE.finditer(getattr(owner, attr)):
                token, _suffix = split_trailing_punctuation(match.group(0))
                report.add(
                    rules.LINK001,
                    "Visible URL/email address is not represented by a hyperlink element.",
                    location=context_location(block, kind, counts[kind]),
                    details={"text": token},
                )


def _audit_empty_spacers(document: OdfDocument, report: Report) -> None:
    catalog = catalog_of(document)
    styles = []
    breaks = 0
    for paragraph in spacer_candidates(document.tree(Part.CONTENT)):
        name = paragraph.get(qn("text", "style-name"))
        try:
            breaks += catalog.has_break_semantics(name)
        except RemediationError:
            continue  # the style summary reports these unresolved current-flow styles
        styles.append(name)
    if styles:
        report.add(
            rules.LAYOUT001,
            (
                "Empty body paragraphs were found. If they are only visual "
                "spacers, prefer paragraph spacing instead."
            ),
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
        report.add(
            rules.STYLE002,
            "Blinking text styling is present.",
            location=Location(Part.STYLES.value),
        )


def _audit_style_summary(document: OdfDocument, report: Report) -> None:
    rows, problems = _style_rows(document)
    report.facts[FactKeys.TEXT_PARAGRAPH_STYLES] = rows
    if problems:
        report.add(
            rules.STYLE001, location=Location(Part.STYLES.value), details={"styles": problems}
        )


def _style_rows(document: OdfDocument) -> tuple[list[StyleUsage], dict[str, str]]:
    counts: Counter[str] = Counter()
    problems = {}
    for node in text_nodes(
        document.tree(Part.CONTENT), qn("text", "p"), qn("text", "h"), main_only=True
    ):
        name = node.get(qn("text", "style-name")) or "(none)"
        try:
            paragraph_style_name(node)
        except RemediationError as exc:
            problems[name] = str(exc)
        else:
            counts[name] += 1
    catalog = catalog_of(document)
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
        except RemediationError as exc:
            problems[name] = str(exc)
    return rows, problems
