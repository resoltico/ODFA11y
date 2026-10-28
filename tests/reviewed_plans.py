# SPDX-License-Identifier: MPL-2.0
"""Author bound application plans from explicit expected-operation fixture values."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from odfa11y.content import (
    SHAPE_TAGS,
    GraphicIdentity,
    document_links,
    eligible_text_node,
    link_fingerprint,
    link_location,
    page_fingerprint,
    page_location,
    pages,
    table_fingerprint,
)
from odfa11y.decisions import Decision, decode_answer
from odfa11y.errors import PackageError
from odfa11y.families.database.descriptions import fingerprint as database_fingerprint
from odfa11y.families.database.descriptions import targets as database_targets
from odfa11y.families.spreadsheet.sheets import sheet_name, sheets
from odfa11y.families.spreadsheet.snapshot import sheet_fingerprint
from odfa11y.families.text.contexts import context_location, text_nodes
from odfa11y.families.text.headings import heading_fingerprint, heading_location
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.plans import Plan, PlanHeader, SourceBinding, registered_kinds
from odfa11y.report import Location

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import DecisionKind, OpenDecision
    from odfa11y.report import Finding, Report


def reviewed_plan(
    source: str | Path, expected: Sequence[Operation] = (), fidelity: FidelityPolicy | None = None
) -> Plan:
    """Build explicit fixture answers, preserving stale fingerprints when intentionally supplied.

    This is test data authoring. The product accepts no operation-list plan format.

    Returns
    -------
    Plan
        Actual registered answers, source-bound before invoking the application.

    """
    source = Path(source)
    try:
        document = OdfDocument.open(source)
    except PackageError, OSError:
        document = None
    answers = []
    kinds = registered_kinds()
    for operation in expected:
        values = operation.as_dict()
        name = values.pop("operation")
        if name in {
            "set_metadata",
            "set_odf_version",
            "normalize_spacing",
            "set_formula_alternative",
        }:
            kind_id = {
                "set_metadata": "document.metadata",
                "set_odf_version": "document.odf_version",
                "normalize_spacing": "text.spacing",
                "set_formula_alternative": "formula.alternative",
            }[name]
            fields = {
                key: value
                for key, value in values.items()
                if value is not None and key != "fingerprint"
            }
            if name == "set_formula_alternative":
                fields["alternative"] = fields.pop("text")
            if fields:
                kind = kinds[kind_id]
                answers.append(
                    Decision(kind, None, None, decode_answer(kind.answer_type, fields, kind_id))
                )
        elif name in {"linkify_addresses", "remove_empty_spacers"}:
            kind_id = (
                "text.linkify_addresses" if name == "linkify_addresses" else "text.remove_spacers"
            )
            kind = kinds[kind_id]
            answers.append(
                Decision(
                    kind, None, None, decode_answer(kind.answer_type, {"enabled": True}, kind_id)
                )
            )
        else:
            answers.extend(_target_answers(document, name, values["entries"], kinds))
    if source.is_file():
        return Plan.for_source(source, answers, fidelity=fidelity)

    return Plan(
        PlanHeader(1, SourceBinding("0" * 64), "0.8.0"),
        tuple(answers),
        fidelity or FidelityPolicy(),
    )


def _target_answers(
    document: OdfDocument | None,
    name: str,
    entries: Mapping[str, Any],
    kinds: Mapping[str, DecisionKind],
) -> list[Decision]:
    answers = []
    for key, raw in entries.items():
        fields = dict(raw) if isinstance(raw, dict) else {"name": raw}
        fingerprint = fields.pop("fingerprint", None)
        if name == "set_graphic_alternatives":
            kind_id = "graphic.alternative"
            target, current = _graphic(document, key)
            payloads = [(kind_id, target, fields, fingerprint or current)]
        elif name == "set_heading_levels":
            kind_id = "heading.level"
            current = _heading(document, key)
            payloads = [(kind_id, key, fields, fingerprint or current)]
        elif name == "mark_table_headers":
            target, current = _table(document, key)
            payloads = [("table.headers", target, fields, fingerprint or current)]
        elif name == "set_sheet_names":
            target, current = _sheet(document, key)
            payloads = [("sheet.name", target, fields, fingerprint or current)]
        elif name == "set_link_descriptions":
            current = (
                next(
                    (
                        link_fingerprint(document, link)
                        for index, link in enumerate(document_links(document), 1)
                        if link_location(link, index).path == key
                    ),
                    "0" * 16,
                )
                if document
                else "0" * 16
            )
            payloads = [("link.description", key, fields, fingerprint or current)]
        elif name == "set_page_semantics":
            payloads = _page_answers(document, key, fields, fingerprint)
        elif name == "set_database_descriptions":
            matches = database_targets(document).get(key, []) if document else []
            payloads = [
                (
                    "database.description",
                    key,
                    fields,
                    fingerprint
                    or (database_fingerprint(matches[0]) if len(matches) == 1 else "0" * 16),
                )
            ]
        else:
            msg = f"Fixture needs explicit decision authoring for {name}"
            raise AssertionError(msg)
        for kind_id, target, values, reviewed in payloads:
            kind = kinds[kind_id]
            answers.append(
                Decision(
                    kind,
                    Location(target),
                    reviewed,
                    decode_answer(kind.answer_type, values, kind_id),
                )
            )
    return answers


def _graphic(document: OdfDocument | None, key: str) -> tuple[str, str]:
    if document is not None:
        frames = [
            node
            for node in select_elements(document.tree(Part.CONTENT), "//office:body//*")
            if node.tag in SHAPE_TAGS and node.tag != qn("draw", "g") and eligible_text_node(node)
        ]
        identity = GraphicIdentity(document, frames)
        matches = identity.matching(key)
        if matches:
            target = identity.target(matches[0])
            return target, identity.fingerprint(identity.matching(target))
    return (
        key if key.startswith("content/") else f"content/frame[name={quote(key, safe='')}]"
    ), "0" * 16


def _heading(document: OdfDocument | None, key: str) -> str:
    if document:
        for index, node in enumerate(
            text_nodes(document.tree(Part.CONTENT), qn("text", "h"), main_only=True), 1
        ):
            if heading_location(node, index).path == key:
                return heading_fingerprint(node, document)
    return "0" * 16


def _table(document: OdfDocument | None, key: str) -> tuple[str, str]:
    if document:
        for index, node in enumerate(
            text_nodes(document.tree(Part.CONTENT), qn("table", "table")), 1
        ):
            target = context_location(node, "table", index, node.get(qn("table", "name"))).path
            if key in {target, node.get(qn("table", "name"))}:
                return target, table_fingerprint(node, document)
    return (
        key if key.startswith("content/") else f"content/table[name={quote(key, safe='')}]"
    ), "0" * 16


def _sheet(document: OdfDocument | None, key: str) -> tuple[str, str]:
    if document:
        for index, node in enumerate(sheets(document.tree(Part.CONTENT)), 1):
            target = Location.indexed(Part.CONTENT, "sheet", index).path
            if key in {target, sheet_name(node)}:
                return target, sheet_fingerprint(document, node)
    return key if key.startswith("content/") else "content/sheet[999]", "0" * 16


def _page(document: OdfDocument | None, key: str) -> tuple[str, str]:
    if document:
        for index, node in enumerate(pages(document), 1):
            target = page_location(node, index).path
            if key in {target, node.get(qn("draw", "name"))}:
                return target, page_fingerprint(node, document)
    return (
        key if key.startswith("content/") else f"content/page[name={quote(key, safe='')}]"
    ), "0" * 16


def _page_answers(
    document: OdfDocument | None, key: str, fields: dict[str, Any], fingerprint: str | None
) -> list[tuple[str, str, dict[str, Any], str]]:
    target, current = _page(document, key)
    metadata = {
        field: fields[field] for field in ["title", "description"] if fields.get(field) is not None
    }
    result = [("page.metadata", target, metadata, fingerprint or current)] if metadata else []
    if fields.get("navigation") is not None:
        result.append((
            "page.navigation",
            target,
            {"navigation": fields["navigation"]},
            fingerprint or current,
        ))
    return result


def plan_header(source: Path) -> str:
    """Create the binding header for a literal answer fixture.

    Returns
    -------
    str
        A TOML header binding existing input bytes; absent mock inputs use a fixed digest.

    """
    digest = Plan.for_source(source).header.source.sha256 if source.is_file() else "0" * 64
    return f'[plan]\nformat = 1\ngenerator = "0.8.0"\nsource.sha256 = "{digest}"\n'


def question_for(report: Report, finding: Finding) -> OpenDecision:
    """Select the unique target question motivating one observed finding.

    Returns
    -------
    OpenDecision
        The actual question, independently matched by rule and diagnostic location.

    """
    [question] = [
        item
        for item in report.decisions
        if finding.rule_id in item.rule_ids and item.target == finding.location
    ]
    return question
