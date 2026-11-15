# SPDX-License-Identifier: MPL-2.0
"""Available source questions and authored context for planning and rebinding."""

from dataclasses import replace

from lxml import etree

from odfa11y.concepts.text import visible_words
from odfa11y.decisions import OpenDecision
from odfa11y.decisions.decision import QuestionContext
from odfa11y.errors import DocumentRefusal
from odfa11y.families import require_spec
from odfa11y.odf import Family, OdfDocument
from odfa11y.odf import names as xml_names
from odfa11y.remediate.document_ops import COMMON_KINDS
from odfa11y.targets import Target


def available_questions(document: OdfDocument) -> tuple[OpenDecision, ...]:
    questions = []
    for kind in (*COMMON_KINDS, *require_spec(document.kind).kinds):
        if kind.domain is None:
            questions.append(OpenDecision(kind, None, {}, context=QuestionContext("document")))
            continue
        seen = set()
        for path, node in kind.domain.enumerate(document):
            if path in seen:
                continue
            seen.add(path)
            try:
                target = Target(path, kind.domain.fingerprint(document, node))
            except DocumentRefusal:
                continue  # An unresolved source identity is unavailable for an override.
            questions.append(
                OpenDecision(
                    kind,
                    target,
                    {},
                    context=_context(document, node),
                )
            )
    return tuple(questions)


def with_context(question: OpenDecision, available: tuple[OpenDecision, ...]) -> OpenDecision:
    if question.target is None:
        return question
    match = next(
        (
            item
            for item in available
            if item.kind is question.kind and item.target == question.target
        ),
        None,
    )
    return replace(question, context=match.context) if match else question


def _context(document: OdfDocument, node: etree._Element) -> QuestionContext:
    page = next(
        (
            ancestor
            for ancestor in (node, *node.iterancestors())
            if ancestor.tag == xml_names.DRAW_PAGE
        ),
        None,
    )
    sheet = next(
        (
            ancestor
            for ancestor in (node, *node.iterancestors())
            if ancestor.tag == xml_names.TABLE_TABLE
        ),
        None,
    )
    family = document.kind.family if document.kind else None
    page_name = page.get(xml_names.DRAW_NAME) if page is not None else None
    name = node.get(xml_names.DRAW_NAME) or node.get(xml_names.TABLE_NAME)
    return QuestionContext(
        etree.QName(node).localname,
        visible_words(node) or None,
        name,
        page=page_name if family is Family.DRAWING else None,
        slide=page_name if family is Family.PRESENTATION else None,
        sheet=sheet.get(xml_names.TABLE_NAME)
        if sheet is not None and family is Family.SPREADSHEET
        else None,
    )
