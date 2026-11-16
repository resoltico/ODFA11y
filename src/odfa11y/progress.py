# SPDX-License-Identifier: MPL-2.0
"""progress vocabulary."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum


class Step(StrEnum):
    """Fixed progress identities, independent of presenter labels."""

    PREPARE = "prepare"
    IDENTIFY_SOURCE = "identify-source"
    AUDIT_SOURCE = "audit-source"
    REMEDIATE = "remediate"
    AUDIT_REMEDIATED = "audit-remediated"
    EXPORT_SOURCE = "export-source"
    EXPORT_REMEDIATED = "export-remediated"
    AUDIT_PDF = "audit-pdf"
    VALIDATE_PDF = "validate-pdf"
    FIDELITY = "fidelity"
    PUBLISH_EVIDENCE = "publish-evidence"
    LOAD_PLAN = "load-plan"
    PIPELINE = "pipeline"
    AUDIT_DOCUMENT = "audit-document"
    EXPORT_PDF = "export-pdf"
    EXPORT_CANDIDATE = "export-candidate"
    COMPARE_FIDELITY = "compare-fidelity"
    PROBE_CAPABILITIES = "probe-capabilities"
    PROBE_TOOLCHAIN = "probe-toolchain"
    BATCH_ITEM = "batch-item"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.PREPARE: "Validate inputs, capture source and resolve the required tools.",
            self.IDENTIFY_SOURCE: "Establish the captured source document identity.",
            self.AUDIT_SOURCE: "Inspect accessibility conditions in the source document.",
            self.REMEDIATE: "Apply the reviewed decisions under preservation guards.",
            self.AUDIT_REMEDIATED: "Inspect the candidate after applying reviewed decisions.",
            self.EXPORT_SOURCE: "Export the captured source to PDF.",
            self.EXPORT_REMEDIATED: "Export the remediation candidate to PDF.",
            self.AUDIT_PDF: "Inspect the exported PDF structure and content.",
            self.VALIDATE_PDF: "Validate the exported PDF against PDF/UA with veraPDF.",
            self.FIDELITY: "Compare the source and candidate exports under the fidelity policy.",
            self.PUBLISH_EVIDENCE: "Publish the declared evidence artifacts and review record.",
            self.LOAD_PLAN: "Load and validate the reviewed plan.",
            self.PIPELINE: "Execute the selected assurance workflow.",
            self.AUDIT_DOCUMENT: "Inspect one OpenDocument or PDF input.",
            self.EXPORT_PDF: "Export an original document to PDF.",
            self.EXPORT_CANDIDATE: "Render a candidate input for comparison.",
            self.COMPARE_FIDELITY: "Compare the original input artifacts for fidelity.",
            self.PROBE_CAPABILITIES: (
                "Measure a declared native capability with a synthetic document."
            ),
            self.PROBE_TOOLCHAIN: "Identify the native tools and their available capabilities.",
            self.BATCH_ITEM: "Execute one identified batch item.",
        }[self]


class _StageMeaning:
    value: str

    @property
    def meaning(self) -> str:
        return Step(self.value).meaning


_NON_STAGE_STEPS = {
    Step.PREPARE,
    Step.AUDIT_DOCUMENT,
    Step.EXPORT_PDF,
    Step.EXPORT_CANDIDATE,
    Step.COMPARE_FIDELITY,
    Step.PROBE_CAPABILITIES,
    Step.PROBE_TOOLCHAIN,
    Step.BATCH_ITEM,
}
Stage = StrEnum(
    "Stage",
    {step.name: step.value for step in Step if step not in _NON_STAGE_STEPS},
    type=_StageMeaning,
)


PIPELINE_STAGES = (
    Stage.IDENTIFY_SOURCE,
    Stage.AUDIT_SOURCE,
    Stage.REMEDIATE,
    Stage.AUDIT_REMEDIATED,
    Stage.EXPORT_SOURCE,
    Stage.EXPORT_REMEDIATED,
    Stage.AUDIT_PDF,
    Stage.VALIDATE_PDF,
    Stage.FIDELITY,
)


class StepState(StrEnum):
    """Progress lifetime; interruptions and execution errors both fail a step."""

    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.RUNNING: "The operation is in progress.",
            self.PASSED: "The operation completed successfully.",
            self.FAILED: "The operation failed or was interrupted.",
            self.SKIPPED: "The operation did not run.",
        }[self]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """One path-free observation of an operation's progress."""

    step: Step
    state: StepState
    item: str | None = None


ProgressObserver = Callable[[ProgressEvent], None]


@dataclass(slots=True)
class StepProgress:
    state: StepState = StepState.PASSED


@contextmanager
def step(
    observer: ProgressObserver | None, kind: Step, *, item: str | None = None
) -> Generator[StepProgress]:
    if observer:
        observer(ProgressEvent(kind, StepState.RUNNING, item))
    progress = StepProgress()
    try:
        yield progress
    except BaseException:
        progress.state = StepState.FAILED
        raise
    finally:
        if observer:
            observer(ProgressEvent(kind, progress.state, item))
