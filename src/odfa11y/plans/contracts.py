# SPDX-License-Identifier: MPL-2.0
"""Annotated file and decision projections derived from the kind catalogue."""

from collections.abc import Mapping
from dataclasses import dataclass, field, make_dataclass
from functools import reduce
from operator import or_
from types import GenericAlias
from typing import Literal, Protocol, cast

from odfa11y.contracts import fields_of, mapping_contract
from odfa11y.decisions import Decision, DecisionKind, DecisionScope
from odfa11y.decisions.decision import QuestionContext
from odfa11y.errors import PlanError
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
from odfa11y.plans.model import Plan, PlanHeader, UnansweredDecision
from odfa11y.targets import Fingerprint, Target, TargetPath


@dataclass(frozen=True, slots=True)
class PlanFile[T]:
    """The source binding, decision tables and fidelity policy in a plan file."""

    plan: PlanHeader
    decisions: T = field(default_factory=dict)
    fidelity: FidelityPolicy = field(default_factory=Pagination.SAME)


class _TargetBinding(Protocol):
    @property
    def fingerprint(self) -> Fingerprint: ...


@dataclass(frozen=True, slots=True)
class UnansweredDocument:
    """A header-only document policy block."""


@dataclass(frozen=True, slots=True)
class UnansweredTarget:
    """An advisory target fingerprint without an active answer."""

    fingerprint: str | None = None


def target_answer(kind: DecisionKind) -> type[object]:
    return make_dataclass(
        kind.answer_type.__name__ + "Target",
        [("fingerprint", Fingerprint)],
        bases=(kind.answer_type,),
        frozen=True,
        slots=True,
        kw_only=True,
    )


def file_contract(kinds: Mapping[str, DecisionKind]) -> object:
    tables = {
        kind.id: reduce(or_, (kind.answer_type, UnansweredDocument))
        if kind.scope is DecisionScope.DOCUMENT
        else dict.__class_getitem__((
            TargetPath,
            reduce(or_, (target_answer(kind), UnansweredTarget)),
        ))
        for kind in kinds.values()
    }
    return GenericAlias(PlanFile, mapping_contract("PlanDecisions", tables, total=False))


def decision_contract(kinds: Mapping[str, DecisionKind], *, open_decision: bool) -> object:
    variants = []
    for kind in kinds.values():
        fields = {
            "kind_id": Literal.__getitem__((kind.id,)),
            "target": Target if kind.scope is DecisionScope.TARGET else type(None),
        }
        if open_decision:
            fields |= {
                "current": Mapping[str, object],
                "rule_ids": tuple[str, ...],
                "context": QuestionContext | None,
            }
        else:
            fields["answer"] = kind.answer_type
        variants.append(mapping_contract(kind.answer_type.__name__ + "Decision", fields))
    if not variants:
        return mapping_contract("NoDecisions", {})
    return reduce(or_, variants)


def to_file(plan: Plan) -> PlanFile[dict[str, object]]:
    tables: dict[str, object] = {}
    for decision in plan.decisions:
        if decision.target is None:
            tables[decision.kind.id] = decision.answer
            continue
        values = {
            field.name: getattr(decision.answer, field.name)
            for field in fields_of(decision.kind.answer_type)
        }
        entry = target_answer(decision.kind)(**values, fingerprint=decision.target.fingerprint)
        group = cast(dict[str, object], tables.setdefault(decision.kind.id, {}))
        group[decision.target.path] = entry
    for question in plan.unanswered:
        if question.path is None:
            tables[question.kind_id] = UnansweredDocument()
        else:
            group = cast(dict[str, object], tables.setdefault(question.kind_id, {}))
            group[question.path] = UnansweredTarget(question.fingerprint)
    return PlanFile(plan.header, tables, plan.fidelity)


def from_file(record: PlanFile[Mapping[str, object]], kinds: Mapping[str, DecisionKind]) -> Plan:
    decisions = []
    unanswered = []
    problems = []
    for kind_id, payload in record.decisions.items():
        kind = kinds[kind_id]
        if kind.scope is DecisionScope.DOCUMENT:
            if isinstance(payload, UnansweredDocument):
                unanswered.append(UnansweredDecision(kind_id, None))
                continue
            decisions.append(Decision._decoded(kind, None, payload))
            continue
        for path, entry in cast(Mapping[TargetPath, object], payload).items():
            if isinstance(entry, UnansweredTarget):
                unanswered.append(UnansweredDecision(kind_id, path, entry.fingerprint))
                continue
            fields = {
                field.name: getattr(entry, field.name) for field in fields_of(kind.answer_type)
            }
            answer = kind.answer_type(**fields)
            try:
                target = Target(path, cast(_TargetBinding, entry).fingerprint)
                decisions.append(Decision._decoded(kind, target, answer))
            except PlanError as error:
                problems.append(f"{kind_id}.{path}: {error}")
    if problems:
        message = "Plan targets could not be bound"
        raise PlanError(message, problems=tuple(problems))
    return Plan._decoded(record.plan, tuple(decisions), record.fidelity, tuple(unanswered))
