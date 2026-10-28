# SPDX-License-Identifier: MPL-2.0
"""Shared exit, execution, progress and human-review vocabulary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

from odfa11y.errors import UsageError

if TYPE_CHECKING:
    from collections.abc import Iterable


class ExitStatus(IntEnum):
    """Public command outcomes; precedence is independent of numeric values."""

    PASSED = 0
    STRICT_WARNINGS = 1
    ERRORS = 2
    EXECUTION_FAILURE = 3
    USAGE_ERROR = 4


EXIT_PRECEDENCE = (
    ExitStatus.PASSED,
    ExitStatus.STRICT_WARNINGS,
    ExitStatus.ERRORS,
    ExitStatus.USAGE_ERROR,
    ExitStatus.EXECUTION_FAILURE,
)


def combine_statuses(statuses: Iterable[ExitStatus | int]) -> ExitStatus:
    """Combine outcomes by their explicit public precedence.

    Returns
    -------
    ExitStatus
        The strongest outcome, or passed for empty input.

    """
    present = {ExitStatus(status) for status in statuses}
    return next(
        (status for status in reversed(EXIT_PRECEDENCE) if status in present), ExitStatus.PASSED
    )


def failure_status(error: BaseException) -> ExitStatus:
    """Classify an expected input error separately from execution failure.

    Returns
    -------
    ExitStatus
        Usage error for invalid arguments/plans, execution failure otherwise.

    """
    return ExitStatus.USAGE_ERROR if isinstance(error, UsageError) else ExitStatus.EXECUTION_FAILURE


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


class StageStatus(StrEnum):
    """The outcome or applicability of one pipeline stage."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not-applicable"


class RunStatus(StrEnum):
    """Overall pipeline assurance result."""

    PASSED = StageStatus.PASSED
    FAILED = StageStatus.FAILED


class BatchStatus(StrEnum):
    """Execution lifetime of a batch or one manifest item."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


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


class ReviewTopic(StrEnum):
    """Shared human-review subjects; each family supplies its own guidance."""

    ALT_TEXT = "alt-text"
    CHART_MEANING = "chart-meaning"
    COLOUR = "colour"
    COLOUR_AND_LAYOUT = "colour-and-layout"
    DATABASE_MEANING = "database-meaning"
    EXPORT_BOUNDARY = "export-boundary"
    HEADER_CELLS = "header-cells"
    HEADINGS = "headings"
    HIDDEN_CONTENT = "hidden-content"
    IMAGE_MEANING = "image-meaning"
    LABELS_AND_RANGES = "labels-and-ranges"
    LANGUAGE = "language"
    LAYERS_AND_ANNOTATIONS = "layers-and-annotations"
    LAYOUT = "layout"
    LINK_PURPOSE = "link-purpose"
    MATHEMATICS = "mathematics"
    PAGE_TITLES = "page-titles"
    PRIVACY_AND_EXECUTION = "privacy-and-execution"
    READING_ORDER = "reading-order"
    SHEET_NAMES = "sheet-names"
    SLIDES_AND_NOTES = "slides-and-notes"
    SOURCE_ASSURANCE = "source-assurance"
    SOURCE_BOUNDARY = "source-boundary"
    TABLE_HEADERS = "table-headers"


class ViolationKind(StrEnum):
    """Structured reasons a remediation candidate cannot be published."""

    FAILED_OUTCOME = "failed-outcome"
    PROTECTED_CONTENT = "protected-content"
    OPAQUE_RESOURCE = "opaque-resource"
    SCHEMA_REGRESSION = "schema-regression"
    EDIT_ACCOUNTING = "edit-accounting"
    FOREIGN_OPERATION = "foreign-operation"
