# SPDX-License-Identifier: MPL-2.0
"""Execute reviewed decisions and return every outcome and publication guard violation."""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
lazy from collections.abc import Sequence

from odfa11y.audit.engine import audit_document
from odfa11y.capture import capture_source, source_digest
from odfa11y.concepts import opaque_payloads
from odfa11y.concepts.preservation import ProtectedPackage
from odfa11y.decisions import Decision
from odfa11y.decisions.constraints import check_plan
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal, OutputOccupied, PackageError, PlanError
from odfa11y.families import require_spec
from odfa11y.odf import OdfDocument, Use, regressions, validate
from odfa11y.odf.allowance import Allowance
from odfa11y.plans import Plan
from odfa11y.plans.registry import load_plan
from odfa11y.records import SchemaCheck
from odfa11y.remediate.compile import compile_decisions
from odfa11y.remediate.document_ops import COMMON_KINDS
from odfa11y.remediate.result import (
    DecisionPrediction,
    RemediationResult,
    UnansweredReview,
    Violation,
)
from odfa11y.remediate.violations import ViolationKind
from odfa11y.report import Finding, Report
from odfa11y.status import StageStatus
lazy from odfa11y.odf import SchemaResult


def remediate(
    source: str | Path,
    destination: str | Path,
    plan: Plan | str | Path,
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Apply a bound plan under source, family, preservation and schema guards.

    Returns
    -------
    RemediationResult
        All outcomes and violations; published is true only after an actual write.

    """
    source = Path(source)
    destination = Path(destination)
    _require_distinct(source, destination)
    with (
        tempfile.TemporaryDirectory(prefix="odfa11y-remediate-") as directory,
        capture_source(source, directory=Path(directory)) as captured,
    ):
        document = _document(captured, destination)
        digest = source_digest(captured)
        if not isinstance(plan, Plan):
            plan = load_plan(plan, document=document, source_sha256=digest)
        decisions = compile_decisions(document, plan, source_sha256=digest)
        return _execute(document, source, destination, decisions, dry_run=dry_run, plan=plan)


def _document(source: Path, destination: Path) -> OdfDocument:
    _require_distinct(source, destination)
    document = OdfDocument.open(source)
    document.require(Use.REMEDIATE)
    if document.kind is None:
        msg = "Source is not a recognised OpenDocument document"
        raise PackageError(msg)
    _require_consistent_kind(document, source)
    return document


@dataclass(slots=True)
class _Execution:
    outcomes: list[Outcome] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    usable: bool = True
    allowance: Allowance = field(default_factory=Allowance)


def _execute(
    document: OdfDocument,
    source: Path,
    destination: Path,
    decisions: Sequence[Decision],
    *,
    dry_run: bool,
    plan: Plan | None = None,
) -> RemediationResult:
    require_spec(document.kind)
    before = ProtectedPackage.capture(document)
    opaque_before = opaque_payloads(document)
    schema_before = validate(document)
    audit_before = audit_document(document, subject=source.name)
    unanswered = _unanswered(document, plan) if plan else ()
    state = _run_decisions(document, decisions)
    schema = _postconditions(document, before, opaque_before, schema_before, state=state)
    candidate = audit_document(document, subject=source.name)
    predictions = (
        tuple(_predict(decision, audit_before, candidate) for decision in plan.decisions)
        if plan is not None
        else ()
    )
    published = not dry_run and not state.violations
    if published:
        document.save(destination)
    return RemediationResult(
        _source=source,
        _destination=destination if published else None,
        outcomes=tuple(state.outcomes),
        schema=schema,
        published=published,
        violations=tuple(state.violations),
        dry_run=dry_run,
        decisions=tuple(decisions),
        predictions=predictions,
        candidate=candidate,
        unanswered=unanswered,
    )


def _unanswered(document: OdfDocument, plan: Plan) -> tuple[UnansweredReview, ...]:
    reviews = []
    applicable = (*COMMON_KINDS, *require_spec(document.kind).kinds)
    for question in plan.unanswered:
        kind = question.kind
        reason = None
        if kind not in applicable:
            reason = "The decision kind is unavailable for this source family."
        elif question.path is not None and kind.domain is not None:
            try:
                current = kind.domain.binding(document, question.path)
                if question.fingerprint is not None and current.fingerprint != question.fingerprint:
                    reason = (
                        "The target fingerprint changed since this unanswered block was generated."
                    )
            except (PlanError, DocumentRefusal) as error:
                reason = error.message
        reviews.append(
            UnansweredReview(question.kind_id, question.path, reason is not None, reason)
        )
    return tuple(reviews)


def _predict(decision: Decision, before: Report, after: Report) -> DecisionPrediction:
    def related(finding: Finding) -> bool:
        if finding.rule not in decision.kind.resolves:
            return False
        return decision.target is None or (
            finding.location is not None and finding.location.path == decision.target.path
        )

    previous = tuple(finding for finding in before.findings if related(finding))
    remaining = tuple(finding for finding in after.findings if related(finding))
    keys = {(finding.rule.id, finding.location) for finding in remaining}
    resolved = tuple(
        finding for finding in previous if (finding.rule.id, finding.location) not in keys
    )
    return DecisionPrediction(
        decision.kind.id, decision.target.path if decision.target else None, resolved, remaining
    )


def _run_decisions(document: OdfDocument, decisions: Sequence[Decision]) -> _Execution:
    state = _Execution()
    try:
        check_plan(document, decisions)
    except DocumentRefusal as exc:
        state.violations.append(Violation(ViolationKind.FOREIGN_OPERATION, str(exc)))
        state.outcomes.extend(
            Outcome(decision.kind.id, Status.FAILED, exc.message, failure=exc.as_record())
            for decision in decisions
        )
        return state
    for index, decision in enumerate(decisions):
        _run_decision(document, decision, state)
        if not state.usable:
            state.outcomes.extend(
                Outcome(
                    remaining.kind.id,
                    Status.FAILED,
                    "Not run after document-model integrity failure",
                )
                for remaining in decisions[index + 1 :]
            )
            break
    return state


def _run_decision(document: OdfDocument, decision: Decision, state: _Execution) -> None:
    before = document.checkpoint()
    xml_before = ProtectedPackage.capture(document)
    allowance = Allowance()
    try:
        result = decision.kind.edit(document, decision)
        produced = result.outcomes
        allowance = result.allowance
    except DocumentRefusal as exc:
        produced = (Outcome(decision.kind.id, Status.FAILED, exc.message, failure=exc.as_record()),)
    state.outcomes.extend(produced)
    state.violations.extend(
        Violation(ViolationKind.FAILED_OUTCOME, outcome.message, outcome.kind_id, outcome.target)
        for outcome in produced
        if outcome.status == Status.FAILED
    )
    try:
        changed = document.changed_since(before)
    except PackageError as exc:
        state.violations.append(
            Violation(ViolationKind.PROTECTED_CONTENT, str(exc), decision.kind.id)
        )
        state.usable = False
        return
    if problem := _check_edit_accounting(decision, produced, changed):
        state.violations.append(Violation(ViolationKind.EDIT_ACCOUNTING, problem, decision.kind.id))
    state.allowance |= allowance
    if not xml_before.preserved(ProtectedPackage.capture(document), allowance):
        state.violations.append(
            Violation(
                ViolationKind.PROTECTED_CONTENT,
                "Protected document content changed during remediation",
                decision.kind.id,
            )
        )


def _postconditions(
    document: OdfDocument,
    before: ProtectedPackage,
    opaque_before: tuple[tuple[str, str], ...],
    schema_before: SchemaResult,
    *,
    state: _Execution,
) -> SchemaCheck:
    if not state.usable:
        return SchemaCheck(
            StageStatus.SKIPPED,
            None,
            schema_before.count if schema_before.available else None,
            None,
            None,
            None,
        )
    if not before.preserved(ProtectedPackage.capture(document), state.allowance):
        state.violations.append(
            Violation(
                ViolationKind.PROTECTED_CONTENT,
                "Protected document content changed during remediation",
            )
        )
    if opaque_payloads(document) != opaque_before:
        state.violations.append(
            Violation(
                ViolationKind.OPAQUE_RESOURCE,
                "Opaque document resources changed during remediation",
            )
        )
    result, violation = _schema_check(schema_before, validate(document))
    if violation:
        state.violations.append(violation)
    return result


def _schema_check(
    before: SchemaResult, after: SchemaResult
) -> tuple[SchemaCheck, Violation | None]:
    if not after.available:
        return SchemaCheck(
            StageStatus.SKIPPED,
            after.version,
            before.count if before.available else None,
            None,
            None,
            None,
        ), None
    new = regressions(before, after) if before.available else after.messages()
    count = sum(len(messages) for messages in new.values())
    check = SchemaCheck(
        StageStatus.FAILED if count else StageStatus.PASSED,
        after.version,
        before.count if before.available else None,
        after.count,
        count,
        after.unlocated,
    )
    if not count:
        return check, None
    messages = "; ".join(
        f"{member}: {message}" for member, found in new.items() for message in found
    )
    reason = (
        "Remediation introduced ODF schema violations"
        if before.available
        else (
            "The source's ODF version has no bundled schema, so the result must "
            f"validate against ODF {after.version} outright"
        )
    )
    return check, Violation(ViolationKind.SCHEMA_REGRESSION, reason + ": " + messages)


def _require_consistent_kind(document: OdfDocument, source: Path) -> None:
    detection = document.detection
    kind = detection.kind
    if kind is None:
        return  # refused earlier, with its own message
    if detection.manifest_media_type not in {None, detection.media_type}:
        msg = f"{source.name}: manifest and mimetype disagree about the kind; nothing was written."
        raise PackageError(msg)
    if kind.body_element is not None and detection.body_element != kind.body_element:
        msg = (
            f"{source.name}: the body is {detection.body_element!r}, not the "
            f"{kind.body_element!r} its media type promises; nothing was written."
        )
        raise PackageError(msg)


def _require_distinct(source: Path, destination: Path) -> None:
    same = source.resolve() == destination.resolve() or (
        destination.exists() and source.exists() and Path(source).samefile(destination)
    )
    if same:
        msg = f"Destination must differ from the source: {destination.name}"
        raise OutputOccupied(msg)


def _check_edit_accounting(
    decision: Decision, outcomes: Sequence[Outcome], changed: frozenset[str]
) -> str | None:
    applied = any(o.status is Status.APPLIED for o in outcomes)
    if applied != bool(changed) and not any(o.status is Status.FAILED for o in outcomes):
        return (
            f"Internal error: decision {decision.kind.id!r} reported "
            f"{'a change' if applied else 'no change'} but changed {len(changed)} XML member(s)."
        )

    return None
