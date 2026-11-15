# SPDX-License-Identifier: MPL-2.0
"""progress vocabulary."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from odfa11y.status import BatchStatus, StageStatus


class StepName(StrEnum):
    """Fixed progress identities, independent of presenter labels."""

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


class StageName(StrEnum):
    """Pipeline execution stages and failure/publication boundaries."""

    IDENTIFY_SOURCE = StepName.IDENTIFY_SOURCE
    AUDIT_SOURCE = StepName.AUDIT_SOURCE
    REMEDIATE = StepName.REMEDIATE
    AUDIT_REMEDIATED = StepName.AUDIT_REMEDIATED
    EXPORT_SOURCE = StepName.EXPORT_SOURCE
    EXPORT_REMEDIATED = StepName.EXPORT_REMEDIATED
    AUDIT_PDF = StepName.AUDIT_PDF
    VALIDATE_PDF = StepName.VALIDATE_PDF
    FIDELITY = StepName.FIDELITY
    PUBLISH_EVIDENCE = StepName.PUBLISH_EVIDENCE
    LOAD_PLAN = StepName.LOAD_PLAN
    PIPELINE = StepName.PIPELINE


PIPELINE_STAGES = (
    StageName.IDENTIFY_SOURCE,
    StageName.AUDIT_SOURCE,
    StageName.REMEDIATE,
    StageName.AUDIT_REMEDIATED,
    StageName.EXPORT_SOURCE,
    StageName.EXPORT_REMEDIATED,
    StageName.AUDIT_PDF,
    StageName.VALIDATE_PDF,
    StageName.FIDELITY,
)


class StepState(StrEnum):
    """Progress lifetime; interruptions and execution errors both fail a step."""

    RUNNING = BatchStatus.RUNNING
    PASSED = StageStatus.PASSED
    FAILED = StageStatus.FAILED
    SKIPPED = StageStatus.SKIPPED


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """One path-free observation of an operation's progress."""

    step: StepName
    state: StepState


ProgressObserver = Callable[[ProgressEvent], None]
