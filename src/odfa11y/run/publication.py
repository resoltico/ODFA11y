# SPDX-License-Identifier: MPL-2.0
"""Publish pipeline evidence and report the actual publication outcome."""

lazy from pathlib import Path

from odfa11y.errors import OdfA11yError
from odfa11y.evidence import Redactor, write_bundle
from odfa11y.progress import ProgressEvent, Step, StepState
lazy from odfa11y.progress import ProgressObserver
lazy from odfa11y.run.record import RunRecord


def publish_evidence(
    source: Path,
    target: Path,
    work: Path,
    record: RunRecord,
    observer: ProgressObserver | None,
) -> None:
    """Gather artifacts and publish a bundle without persisting progress events.

    Observers receive typed ProgressEvent values and must not raise. Publication failures
    and interruption retain their original exceptions and never report success.

    Raises
    ------
    OdfA11yError
        Evidence cannot be published safely.
    OSError
        Artifact collection or publication cannot complete.
    KeyboardInterrupt
        Publication is interrupted.

    """
    if observer is not None:
        observer(ProgressEvent(Step.PUBLISH_EVIDENCE, StepState.RUNNING))
    try:
        artifacts = {
            path.relative_to(work).as_posix(): path
            for path in sorted(work.rglob("*"))
            if path.is_file() and path.relative_to(work).parts[0] != "profile"
        }
        redactor = Redactor.for_locations({
            "profile": work / "profile",
            "work": work,
            "source": source.parent,
            "output": target,
        })
        record.outputs = write_bundle(
            target, record, artifacts, redactor, diagnostics={"verapdf.xml"}
        )
    except OdfA11yError, OSError:
        if observer is not None:
            observer(ProgressEvent(Step.PUBLISH_EVIDENCE, StepState.FAILED))
        raise
    except KeyboardInterrupt:
        if observer is not None:
            observer(ProgressEvent(Step.PUBLISH_EVIDENCE, StepState.FAILED))
        raise
    if observer is not None:
        observer(ProgressEvent(Step.PUBLISH_EVIDENCE, StepState.PASSED))
