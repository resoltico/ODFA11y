# SPDX-License-Identifier: MPL-2.0
"""Author raw human answers, then exercise validated decisions through the real executor."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar, cast

from odfa11y.decisions import Decision, DecisionKind, DecisionScope, decode_answer
from odfa11y.decisions.edit import EditResult, Outcome
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan, PlanHeader, SourceBinding
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import registered_kinds
from odfa11y.remediate.compile import compile_decisions
from odfa11y.remediate.execute import execute_decisions
from odfa11y.targets import Fingerprint, Target, TargetPath


@dataclass(frozen=True, slots=True)
class RawDecision:
    """Unvalidated fixture fields with an optional deliberately supplied stale identity."""

    kind_id: str
    values: Mapping[str, object]
    selector: str | None = None
    fingerprint: object = None


@dataclass(frozen=True)
class FaultEdit(ABC):
    """Inject a faulty edit callback to verify the executor's independent safeguards."""

    name: ClassVar[str]

    @abstractmethod
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]: ...


@dataclass(frozen=True, slots=True)
class FaultInput:
    """Replace only an edit callback while retaining the production answer and target contract."""

    inputs: Authored
    edit: Callable[[OdfDocument, Decision], EditResult]


def fault_input(
    inputs: Authored, edit: Callable[[OdfDocument, Decision], EditResult]
) -> FaultInput:
    return FaultInput(inputs, edit)


def contains_fault(inputs: Iterable[Authored]) -> bool:
    return any(
        isinstance(item, (FaultInput, FaultEdit))
        or (isinstance(item, tuple) and contains_fault(item))
        for item in inputs
    )


type RawFields = dict[str, object]
type RawDecisions = tuple[RawDecision, ...]
type Authored = RawDecision | RawDecisions | Decision | FaultEdit | FaultInput


def _entries(kind_id: str, entries: Mapping[str, RawFields]) -> RawDecisions:
    return tuple(
        RawDecision(
            kind_id,
            {
                key: value
                for key, value in values.items()
                if key != "fingerprint" and value is not None
            },
            selector,
            values.get("fingerprint"),
        )
        for selector, values in entries.items()
    )


def graphic_answer(
    title: object = None,
    description: object = None,
    fingerprint: object = None,
    decorative: object = None,
) -> RawFields:
    return {
        "title": title,
        "description": description,
        "fingerprint": fingerprint,
        "decorative": decorative,
    }


def link_answer(description: object, fingerprint: object = None) -> RawFields:
    return {"description": description, "fingerprint": fingerprint}


def page_answer(
    title: object = None,
    description: object = None,
    navigation: object = None,
    fingerprint: object = None,
) -> RawFields:
    return {
        "title": title,
        "description": description,
        "navigation": navigation,
        "fingerprint": fingerprint,
    }


def header_answer(
    rows: object = None, columns: object = None, fingerprint: object = None
) -> RawFields:
    return {"rows": rows, "columns": columns, "fingerprint": fingerprint}


def level_answer(level: object, fingerprint: object = None) -> RawFields:
    return {"level": level, "fingerprint": fingerprint}


def language_answer(
    western: object = None, asian: object = None, complex: object = None, fingerprint: object = None
) -> RawFields:
    return {"western": western, "asian": asian, "complex": complex, "fingerprint": fingerprint}


def sheet_answer(name: object, fingerprint: object = None) -> RawFields:
    return {"name": name, "fingerprint": fingerprint}


def database_answer(text: object, fingerprint: object = None) -> RawFields:
    return {"text": text, "fingerprint": fingerprint}


def graphic_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("graphic.alternative", entries)


def link_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("link.description", entries)


def header_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("table.headers", entries)


def heading_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("heading.level", entries)


def language_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("language.target", entries)


def sheet_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("sheet.name", entries)


def database_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    return _entries("database.description", entries)


def page_inputs(entries: Mapping[str, RawFields]) -> RawDecisions:
    result = []
    for selector, values in entries.items():
        metadata = {
            key: values[key] for key in ("title", "description") if values.get(key) is not None
        }
        if metadata:
            result.append(
                RawDecision("page.metadata", metadata, selector, values.get("fingerprint"))
            )
        if values.get("navigation") is not None:
            result.append(
                RawDecision(
                    "page.navigation",
                    {"navigation": values["navigation"]},
                    selector,
                    values.get("fingerprint"),
                )
            )
    return tuple(result)


def metadata_input(
    title: object = None, description: object = None, language: object = None
) -> RawDecisions:
    return (
        RawDecision(
            "document.metadata",
            {
                key: value
                for key, value in (
                    ("title", title),
                    ("description", description),
                    ("language", language),
                )
                if value is not None
            },
        ),
    )


def version_input(version: object) -> RawDecisions:
    return (RawDecision("document.odf_version", {"version": version}),)


def formula_input(text: object, fingerprint: object = None) -> RawDecisions:
    return (
        RawDecision("formula.alternative", {"alternative": text}, "content/formula", fingerprint),
    )


def spacing_input(
    reference_text: object,
    target_styles: object,
    exact_reference: object = False,
    include_headings: object = False,
) -> RawDecisions:
    return (
        RawDecision(
            "text.spacing",
            {
                "reference_text": reference_text,
                "target_styles": target_styles,
                "exact_reference": exact_reference,
                "include_headings": include_headings,
            },
        ),
    )


def address_input() -> RawDecisions:
    return (RawDecision("text.linkify_addresses", {"enabled": True}),)


def spacer_input() -> RawDecisions:
    return (RawDecision("text.remove_spacers", {"enabled": True}),)


def materialize(document: OdfDocument | None, inputs: Iterable[Authored]) -> tuple[Decision, ...]:
    result = []
    kinds = registered_kinds()
    for item in inputs:
        if isinstance(item, tuple):
            result.extend(materialize(document, item))
        elif isinstance(item, Decision):
            result.append(item)
        elif isinstance(item, FaultInput):
            result.extend(
                Decision._decoded(
                    replace(decision.kind, edit=item.edit), decision.target, decision.answer
                )
                for decision in materialize(document, (item.inputs,))
            )
        elif isinstance(item, FaultEdit):
            kind = DecisionKind(item.name, DecisionScope.DOCUMENT, type(item), edit=_fault)
            result.append(Decision(kind, None, item))
        else:
            kind = kinds[item.kind_id]
            target = _binding(document, kind, item) if kind.scope is DecisionScope.TARGET else None
            answer = decode_answer(kind.answer_type, item.values, item.kind_id)
            result.append(Decision._decoded(kind, target, answer))
    return tuple(result)


def _fault(document: OdfDocument, decision: Decision[FaultEdit]) -> EditResult:
    return EditResult(decision.answer.apply(document))


def _binding(document: OdfDocument | None, kind: DecisionKind, item: RawDecision) -> Target:
    assert kind.domain is not None
    selector = item.selector or "content/missing"
    available = tuple(kind.domain.enumerate(document)) if document is not None else ()
    # Human-readable fixture names are expanded here; product inputs always use canonical paths.
    matches = [
        (path, node)
        for path, node in available
        if str(path) == selector
        or any(value == selector for name, value in node.attrib.items() if name.endswith("}name"))
    ]
    if matches and document is not None:
        path, node = matches[0]
        current = kind.domain.fingerprint(document, node)
    else:
        path = (
            TargetPath(selector)
            if selector.startswith(("content/", "meta/", "styles/"))
            else TargetPath.named("content", "missing", selector)
        )
        current = Fingerprint("0" * 16)
    return Target(
        path, current if item.fingerprint is None else Fingerprint(cast(str, item.fingerprint))
    )


def apply_in_memory(document: OdfDocument, inputs: Authored) -> tuple[Outcome, ...]:
    """Exercise canonical binding, typed answers and the actual guarded decision runner."""
    decisions = materialize(document, (inputs,))
    plan = Plan(PlanHeader(1, SourceBinding("0" * 64), "test"), decisions, Pagination.SAME())
    ordered = compile_decisions(document, plan)
    return execute_decisions(document, Path("fixture.odf"), ordered, plan=plan).result.outcomes
