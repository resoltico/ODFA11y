# SPDX-License-Identifier: MPL-2.0
"""Apply operations to a document under the postconditions that make a run safe to publish."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.adapter import Status
from odfa11y.errors import OutputError, RemediationError
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument, regressions, validate

from .result import RemediationResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import FamilyAdapter, Operation, Outcome
    from odfa11y.odf import SchemaResult


def remediate(
    source: str | Path,
    destination: str | Path,
    operations: Sequence[Operation],
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Apply operations in order and publish the result only if every postcondition holds.

    Postconditions: every operation belongs to the document's family, no operation failed,
    the family's notion of visible content is preserved (apart from counted spacer removals),
    and the ODF schema reports no violation that the source did not already have. On any
    failure nothing is written.

    Returns
    -------
    RemediationResult
        The per-target outcomes; ``destination`` is None for a dry run.

    Raises
    ------
    RemediationError
        An operation does not apply to this kind of document, an operation failed, content
        changed, or the schema check regressed.

    """
    source, destination = Path(source), Path(destination)
    _require_distinct(source, destination)
    document = OdfDocument.open(source)
    if document.kind is None:
        msg = f"{source.name} is not a recognised OpenDocument document; nothing was written."
        raise RemediationError(msg)
    _require_consistent_kind(document, source)
    adapter = adapter_for(document.kind)
    _require_matching_family(document, adapter, operations)
    snapshot_before = adapter.snapshot(document)
    schema_before = validate(document)

    outcomes: list[Outcome] = []
    for operation in operations:
        edits_before = document.edit_count
        produced = operation.apply(document)
        _check_edit_accounting(operation, produced, document.edit_count - edits_before)
        outcomes.extend(produced)
    failures = [o for o in outcomes if o.status is Status.FAILED]
    if failures:
        lines = [f"{o.operation}{f' [{o.key}]' if o.key else ''}: {o.message}" for o in failures]
        msg = "Remediation failed; nothing was written:\n" + "\n".join(lines)
        raise RemediationError(msg)

    removed = sum(o.removed_blocks for o in outcomes)
    if not adapter.preserved(snapshot_before, adapter.snapshot(document), removed):
        msg = "Visible document content changed during remediation; nothing was written."
        raise RemediationError(msg)
    schema_check = _schema_check(schema_before, validate(document))

    if not dry_run:
        document.save(destination)
    return RemediationResult(
        source=source,
        destination=None if dry_run else destination,
        outcomes=tuple(outcomes),
        schema_check=schema_check,
        dry_run=dry_run,
        operations=tuple(operation.as_dict() for operation in operations),
    )


def _require_matching_family(
    document: OdfDocument, adapter: FamilyAdapter, operations: Sequence[Operation]
) -> None:
    kind = document.kind.name if document.kind is not None else "unrecognised"
    wrong = sorted({op.name for op in operations if op.family not in {None, adapter.family}})
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
        raise RemediationError(msg)
    if kind.body_element is not None and detection.body_element != kind.body_element:
        msg = (
            f"{source.name}: the body is {detection.body_element!r}, not the "
            f"{kind.body_element!r} its media type promises; nothing was written."
        )
        raise RemediationError(msg)


def _require_distinct(source: Path, destination: Path) -> None:
    same = source.resolve() == destination.resolve() or (
        destination.exists() and source.exists() and Path(source).samefile(destination)
    )
    if same:
        msg = f"Destination must differ from the source: {destination.name}"
        raise OutputError(msg)


def _check_edit_accounting(operation: Operation, outcomes: Sequence[Outcome], edits: int) -> None:
    applied = any(o.status is Status.APPLIED for o in outcomes)
    if applied != (edits > 0) and not any(o.status is Status.FAILED for o in outcomes):
        msg = (
            f"Internal error: operation {operation.name!r} reported "
            f"{'a change' if applied else 'no change'} but made {edits} edit(s)."
        )
        raise RemediationError(msg)


def _schema_check(before: SchemaResult, after: SchemaResult) -> str:
    if not after.available:
        return "skipped: no bundled schema for the result's ODF version"
    if not before.available:
        # No baseline to compare with (for example a relabel from ODF 1.2): the result must
        # be fully valid, otherwise the change cannot be shown to be safe.
        if after.count:
            lines = [f"{m}: {x}" for m, found in after.messages().items() for x in found]
            msg = (
                f"The source's ODF version has no bundled schema, so the result must validate "
                f"against ODF {after.version} outright; it has {after.count} violation(s), "
                "nothing was written:\n" + "\n".join(lines)
            )
            raise RemediationError(msg)
        return f"valid against ODF {after.version} (the source's version has no bundled schema)"
    new = regressions(before, after)
    if new:
        lines = [f"{member}: {message}" for member, messages in new.items() for message in messages]
        msg = "Remediation introduced ODF schema violations; nothing was written:\n" + "\n".join(
            lines
        )
        raise RemediationError(msg)
    unlocated = f", {after.unlocated} unlocated" if after.unlocated else ""
    return f"no new violations against ODF {after.version} ({before.count} pre-existing{unlocated})"
