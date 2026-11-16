# SPDX-License-Identifier: AGPL-3.0-only
"""Prepare reviewed source edits and publish only a verified candidate."""

import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from odfa11y.capture import capture_source
from odfa11y.errors import IoFailure
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan
from odfa11y.publish import publish_file, require_distinct, require_file_destination
from odfa11y.remediate.candidate import Candidate, RefusedCandidate
from odfa11y.remediate.catalogue import load_plan
from odfa11y.remediate.compile import compile_decisions
from odfa11y.remediate.execute import execute_decisions, require_remediable
from odfa11y.remediate.result import PublicationState, RemediationResult


def remediate(
    source: str | Path,
    destination: str | Path,
    plan: Plan | str | Path,
    *,
    dry_run: bool = False,
    replace: bool = False,
) -> RemediationResult:
    """Capture and parse once, apply bound decisions, then preview or publish explicitly."""
    source, destination = Path(source), Path(destination)
    try:
        require_distinct(source, destination)
        if not dry_run:
            require_file_destination(destination, replace=replace)
        with capture_source(source) as captured:
            document = OdfDocument.open(captured.path)
            require_remediable(document, source)
            if not isinstance(plan, Plan):
                plan = load_plan(plan, document=document, source_sha256=captured.digest)
            decisions = compile_decisions(document, plan, source_sha256=captured.digest)
            candidate = execute_decisions(document, source, decisions, plan=plan)
            return finish_candidate(
                candidate, source, destination, dry_run=dry_run, replace_existing=replace
            )
    except OSError as error:
        raise IoFailure.from_oserror(error) from error


def finish_candidate(
    candidate: Candidate | RefusedCandidate,
    source: Path,
    destination: Path,
    *,
    dry_run: bool,
    replace_existing: bool = False,
) -> RemediationResult:
    """Publish an unchanged verified model, or retain its explicit preview/refusal."""
    if isinstance(candidate, RefusedCandidate) or dry_run:
        return candidate.result
    require_distinct(source, destination)
    with tempfile.TemporaryDirectory(prefix="odfa11y-candidate-") as temporary:
        path = candidate.materialize(Path(temporary) / destination.name)

        def write(stream) -> None:
            with path.open("rb") as staged:
                shutil.copyfileobj(staged, stream)

        publish_file(destination, write, replace=replace_existing)
    return replace(
        candidate.result,
        _source=source,
        _destination=destination,
        publication=PublicationState.PUBLISHED,
    )
