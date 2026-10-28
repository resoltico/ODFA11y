# SPDX-License-Identifier: MPL-2.0
"""Execute reviewed operations and return every outcome and publication guard violation."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.adapter import Outcome, Status
from odfa11y.content import opaque_payloads
from odfa11y.errors import OutputError, PackageError, RemediationError, UnsupportedKindError
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument, Use, regressions, validate
from odfa11y.outcomes import StageStatus, ViolationKind
from odfa11y.records import SchemaCheck
from odfa11y.source_capture import capture_source

from .planning import compile_operations
from .result import RemediationResult, Violation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import FamilyAdapter, Operation, PreservationSnapshot
    from odfa11y.odf import SchemaResult
    from odfa11y.plans import Plan


def remediate(
    source: str | Path,
    destination: str | Path,
    plan: Plan,
    *,
    dry_run: bool = False,
    rebind: bool = False,
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
        plan.verify_source(captured, rebind=rebind)
        operations = compile_operations(document, plan)
        return _execute(document, source, destination, operations, dry_run=dry_run, rebind=rebind)


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


def _execute(
    document: OdfDocument,
    source: Path,
    destination: Path,
    operations: Sequence[Operation],
    *,
    dry_run: bool,
    rebind: bool = False,
) -> RemediationResult:
    adapter = adapter_for(document.kind)
    before = adapter.snapshot(document)
    opaque_before = opaque_payloads(document)
    schema_before = validate(document)
    state = _run_operations(document, adapter, operations)
    schema = _postconditions(document, adapter, before, opaque_before, schema_before, state=state)
    published = not dry_run and not state.violations
    if published:
        document.save(destination)
    return RemediationResult(
        source=source,
        destination=destination if published else None,
        outcomes=tuple(state.outcomes),
        schema=schema,
        published=published,
        violations=tuple(state.violations),
        rebind=rebind,
        dry_run=dry_run,
        operations=tuple(operation.as_dict() for operation in operations),
    )


def _run_operations(
    document: OdfDocument, adapter: FamilyAdapter, operations: Sequence[Operation]
) -> _Execution:
    state = _Execution()
    try:
        _require_matching_family(document, adapter, operations)
        adapter.preflight(document, operations)
    except (RemediationError, UnsupportedKindError) as exc:
        state.violations.append(Violation(ViolationKind.FOREIGN_OPERATION, str(exc)))
        state.outcomes.extend(
            Outcome(operation.name, Status.FAILED, str(exc)) for operation in operations
        )
        return state
    for index, operation in enumerate(operations):
        _run_operation(document, adapter, operation, state)
        if not state.usable:
            state.outcomes.extend(
                Outcome(
                    remaining.name, Status.FAILED, "Not run after document-model integrity failure"
                )
                for remaining in operations[index + 1 :]
            )
            break
    return state


def _run_operation(
    document: OdfDocument, adapter: FamilyAdapter, operation: Operation, state: _Execution
) -> None:
    before = document.checkpoint()
    protected = None
    try:
        protected = adapter.protect_edit(document, operation)
        produced = operation.apply(document)
    except (RemediationError, UnsupportedKindError) as exc:
        produced = (Outcome(operation.name, Status.FAILED, str(exc)),)
    state.outcomes.extend(produced)
    state.violations.extend(
        Violation(ViolationKind.FAILED_OUTCOME, outcome.message, outcome.operation, outcome.key)
        for outcome in produced
        if outcome.status == Status.FAILED
    )
    try:
        changed = document.changed_since(before)
    except PackageError as exc:
        state.violations.append(
            Violation(ViolationKind.PROTECTED_CONTENT, str(exc), operation.name)
        )
        state.usable = False
        return
    if problem := _check_edit_accounting(operation, produced, changed):
        state.violations.append(Violation(ViolationKind.EDIT_ACCOUNTING, problem, operation.name))
    if protected is not None and not protected():
        state.violations.append(
            Violation(
                ViolationKind.PROTECTED_CONTENT,
                "Protected document content changed during remediation",
                operation.name,
            )
        )


def _postconditions(
    document: OdfDocument,
    adapter: FamilyAdapter,
    before: PreservationSnapshot,
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
    if not adapter.preserved(before, adapter.snapshot(document), state.outcomes):
        state.violations.append(
            Violation(
                ViolationKind.PROTECTED_CONTENT,
                "Visible document content changed during remediation",
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


def _require_matching_family(
    document: OdfDocument, adapter: FamilyAdapter, operations: Sequence[Operation]
) -> None:
    kind = document.kind.name if document.kind is not None else "unrecognised"
    wrong = sorted({
        op.name
        for op in operations
        if op.families is not None and adapter.family not in op.families
    })
    if wrong:
        msg = (
            f"The plan configures {', '.join(wrong)}, which do not apply to a {kind} document "
            f"(handled by the {adapter.name} adapter); nothing was written."
        )
        raise RemediationError(msg)


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
        raise OutputError(msg)


def _check_edit_accounting(
    operation: Operation, outcomes: Sequence[Outcome], changed: frozenset[str]
) -> str | None:
    applied = any(o.status is Status.APPLIED for o in outcomes)
    if applied != bool(changed) and not any(o.status is Status.FAILED for o in outcomes):
        return (
            f"Internal error: operation {operation.name!r} reported "
            f"{'a change' if applied else 'no change'} but changed {len(changed)} XML member(s)."
        )

    return None
