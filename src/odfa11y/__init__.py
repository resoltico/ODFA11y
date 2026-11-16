# SPDX-License-Identifier: AGPL-3.0-only
"""ODFA11y's application API: explicit decisions, guarded workflows and typed results."""

from odfa11y.application import (
    AuditInput,
    AuditResult,
    ComparisonResult,
    ExportResult,
    PlanResult,
    VerificationResult,
    compare,
    doctor,
    export,
    plan,
    verify_evidence,
)
from odfa11y.application import (
    audit as _audit,
)
from odfa11y.application import (
    remediate as _remediate,
)
from odfa11y.application import (
    run as _run,
)
from odfa11y.application.batch import batch as _batch
from odfa11y.application.doctor import DoctorResult
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.batch import BatchRecord
from odfa11y.decisions import Decision, DecisionKind, DecisionScope, OpenDecision, decode_answer
from odfa11y.errors import (
    DocumentRefusal,
    InvalidOption,
    IoFailure,
    OdfA11yError,
    OutputOccupied,
    PlanError,
    Remedy,
    RemedyAction,
    ToolFailure,
    ToolUnavailable,
)
from odfa11y.plans import Plan, PlanHeader, SourceBinding
from odfa11y.progress import ProgressEvent, ProgressObserver, Stage, Step, StepState
from odfa11y.remediate import RemediationResult
from odfa11y.remediate.catalogue import load_plan, registered_kinds
from odfa11y.remediate.result import PublicationState
from odfa11y.report import Location, Report, SarifOptions, render_json, render_sarif
from odfa11y.report.sarif import sarif_failure
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.status import (
    Crashed,
    ExitStatus,
    GateFailed,
    NotApplicable,
    Passed,
    Profile,
    Refused,
    Skipped,
)
from odfa11y.targets import Fingerprint, Target, TargetPath
from odfa11y.version import __version__

__all__ = [
    "AuditInput",
    "AuditResult",
    "BatchRecord",
    "ComparisonResult",
    "Crashed",
    "Decision",
    "DecisionKind",
    "DecisionScope",
    "DoctorResult",
    "DocumentRefusal",
    "ExitStatus",
    "ExportResult",
    "Fingerprint",
    "GateFailed",
    "InvalidOption",
    "IoFailure",
    "Location",
    "NativeTools",
    "NotApplicable",
    "OdfA11yError",
    "OpenDecision",
    "OutputOccupied",
    "Passed",
    "Plan",
    "PlanError",
    "PlanHeader",
    "PlanResult",
    "Profile",
    "ProgressEvent",
    "ProgressObserver",
    "PublicationState",
    "Refused",
    "RemediationResult",
    "Remedy",
    "RemedyAction",
    "Report",
    "RunRecord",
    "SarifOptions",
    "Skipped",
    "SourceBinding",
    "Stage",
    "StageResult",
    "Step",
    "StepState",
    "Target",
    "TargetPath",
    "ToolFailure",
    "ToolUnavailable",
    "Tools",
    "VerificationResult",
    "__version__",
    "audit",
    "batch",
    "compare",
    "decode_answer",
    "doctor",
    "export",
    "load_plan",
    "plan",
    "registered_kinds",
    "remediate",
    "render_json",
    "render_sarif",
    "run",
    "sarif_failure",
    "verify_evidence",
]

audit = _audit
remediate = _remediate
run = _run


batch = _batch
