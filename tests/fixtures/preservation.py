# SPDX-License-Identifier: MPL-2.0
"""Materialize fixed edit intents for the preservation characterisation matrix."""

from collections.abc import Iterator
from pathlib import Path
from typing import cast

from odfa11y.concepts import (
    SHAPE_TAGS,
    GraphicIdentity,
    document_links,
    eligible_text_node,
    link_fingerprint,
    link_location,
    page_fingerprint,
    page_location,
    page_shapes,
    pages,
    shape_identity,
    table_fingerprint,
    visible_words,
)
from odfa11y.decisions import Decision, DecisionKind, DecisionScope, decode_answer
from odfa11y.errors import OdfA11yError
from odfa11y.families.database.descriptions import fingerprint as database_fingerprint
from odfa11y.families.database.descriptions import targets as database_targets
from odfa11y.families.spreadsheet.sheets import sheets
from odfa11y.families.spreadsheet.snapshot import sheet_fingerprint
from odfa11y.families.text.contexts import context_location, text_nodes
from odfa11y.families.text.headings.edit import heading_fingerprint, heading_location
from odfa11y.families.text.language.effective import language_targets
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.families.text.styles.catalogue import NO_STYLE
from odfa11y.odf import Family, OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.plans import Plan
from odfa11y.remediate import remediate
from odfa11y.targets import Fingerprint, Target, TargetPath


def _graphic_targets(document: OdfDocument) -> Iterator[Target]:
    content = document.tree(Part.CONTENT)
    tags = (
        SHAPE_TAGS
        if document.kind and document.kind.family in {Family.PRESENTATION, Family.DRAWING}
        else (xml_names.DRAW_FRAME,)
    )
    frames = [node for node in content.iter() if node.tag in tags and eligible_text_node(node)]
    identity = GraphicIdentity(document, frames)
    seen = set()
    for frame in frames:
        path = identity.target(frame)
        if path not in seen:
            seen.add(path)
            yield Target(TargetPath(path), identity.fingerprint(identity.matching(path)))


def _link_targets(document: OdfDocument) -> Iterator[Target]:
    for index, node in enumerate(document_links(document), 1):
        yield Target(link_location(node, index).path, link_fingerprint(document, node))


def _heading_targets(document: OdfDocument) -> Iterator[Target]:
    content = document.tree(Part.CONTENT)
    for index, node in enumerate(text_nodes(content, xml_names.TEXT_H), 1):
        yield Target(heading_location(node, index).path, heading_fingerprint(node, document))


def _table_targets(document: OdfDocument) -> Iterator[Target]:
    content = document.tree(Part.CONTENT)
    for index, node in enumerate(text_nodes(content, xml_names.TABLE_TABLE), 1):
        yield Target(
            context_location(node, "table", index, node.get(xml_names.TABLE_NAME)).path,
            Fingerprint(table_fingerprint(node, document)),
        )


def _language_targets(document: OdfDocument) -> Iterator[Target]:
    for path, node in language_targets(document).items():
        if visible_words(node):
            yield Target(TargetPath(path), language_fingerprint(document, node))


def _sheet_targets(document: OdfDocument) -> Iterator[Target]:
    content = document.tree(Part.CONTENT)
    for index, node in enumerate(sheets(content), 1):
        yield Target(
            TargetPath.indexed("content", "sheet", index), sheet_fingerprint(document, node)
        )


def _page_targets(document: OdfDocument) -> Iterator[Target]:
    for index, node in enumerate(pages(document), 1):
        yield Target(page_location(node, index).path, page_fingerprint(node, document))


def _database_targets(document: OdfDocument) -> Iterator[Target]:
    for path, nodes in database_targets(document).items():
        if len(nodes) == 1:
            yield Target(TargetPath(path), database_fingerprint(nodes[0]))


_TARGETS = {
    "graphic.alternative": _graphic_targets,
    "link.description": _link_targets,
    "heading.level": _heading_targets,
    "table.headers": _table_targets,
    "language.target": _language_targets,
    "sheet.name": _sheet_targets,
    "page.metadata": _page_targets,
    "page.navigation": _page_targets,
    "database.description": _database_targets,
}


def target_bindings(document: OdfDocument, kind: DecisionKind) -> Iterator[Target]:
    return _TARGETS[kind.id](document)


def answer_values(
    document: OdfDocument, kind: DecisionKind, target: Target | None, index: int
) -> dict[str, object]:
    fixed: dict[str, dict[str, object]] = {
        "document.metadata": {
            "title": "Reviewed document",
            "description": "Reviewed document purpose",
            "language": "en-GB",
        },
        "document.odf_version": {"version": "1.4"},
        "formula.alternative": {"alternative": "Reviewed mathematical expression"},
        "graphic.alternative": {
            "title": "Reviewed graphic",
            "description": "Reviewed graphic meaning",
        },
        "heading.level": {"level": 1},
        "language.target": {"western": "en-GB"},
        "link.description": {"description": "Reviewed destination"},
        "page.metadata": {"title": "Reviewed page", "description": "Reviewed page purpose"},
        "sheet.name": {"name": f"Reviewed {index}"},
        "table.headers": {"rows": 1},
        "text.linkify_addresses": {"enabled": True},
        "text.remove_spacers": {"enabled": True},
    }
    if kind.id in fixed:
        return fixed[kind.id]
    if kind.id == "page.navigation":
        page = next(
            node
            for ordinal, node in enumerate(pages(document), 1)
            if page_location(node, ordinal).path == cast(Target, target).path
        )
        identities = [shape_identity(shape) for shape in page_shapes(page)]
        return {"navigation": list(reversed(identities))}
    if kind.id == "text.spacing":
        paragraphs = [
            node
            for node in text_nodes(document.tree(Part.CONTENT), xml_names.TEXT_P, main_only=True)
            if visible_words(node)
        ]
        if paragraphs:
            return {
                "reference_text": visible_words(paragraphs[0]),
                "target_styles": sorted({
                    node.get(xml_names.TEXT_STYLE_NAME) or NO_STYLE for node in paragraphs
                }),
                "exact_reference": True,
            }
    return {}


def materialize(source: Path, kind: DecisionKind, answers: list[dict[str, object]]) -> Plan:
    document = OdfDocument.open(source)
    available = (
        {str(target.path): target for target in target_bindings(document, kind)}
        if kind.scope is DecisionScope.TARGET
        else {}
    )
    decisions = []
    for entry in answers:
        path = entry["target"]
        target = available[str(path)] if path is not None else None
        answer = decode_answer(kind.answer_type, cast(dict[str, object], entry["answer"]), kind.id)
        decisions.append(Decision._decoded(kind, target, answer))
    return Plan.for_source(source, decisions)


def observation(
    source: Path, kind: DecisionKind, answers: list[dict[str, object]], destination: Path
) -> str:
    if not answers:
        return "no-targets"
    try:
        result = remediate(source, destination, materialize(source, kind, answers))
    except OdfA11yError:
        return "refused"
    return "published" if result.published else "refused"
