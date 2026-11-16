# SPDX-License-Identifier: MPL-2.0
"""ODFA11y's application API: explicit decisions, guarded workflows and typed results."""

from odfa11y.application import (
    AuditInput,
    AuditRun,
    ComparisonResult,
    ExportResult,
    PlanResult,
    VerificationResult,
    compare,
    doctor,
    export,
    plan,
    run_batch,
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
from odfa11y.application.doctor import DoctorResult
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit import plan_blockers
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
from odfa11y.plans.registry import load_plan, registered_kinds
from odfa11y.progress import ProgressEvent, ProgressObserver, Stage, Step, StepState
from odfa11y.remediate import RemediationResult
from odfa11y.report import FORMATS, Location, Report, preflight_sarif, render_reports, terminal_text
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.status import Crashed, ExitStatus, Profile, Refused, failure_status
from odfa11y.targets import Fingerprint, Target, TargetPath
from odfa11y.version import __version__

__all__ = [
    "FORMATS",
    "AuditInput",
    "AuditRun",
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
    "InvalidOption",
    "IoFailure",
    "Location",
    "NativeTools",
    "OdfA11yError",
    "OpenDecision",
    "OutputOccupied",
    "Plan",
    "PlanError",
    "PlanHeader",
    "PlanResult",
    "Profile",
    "ProgressEvent",
    "ProgressObserver",
    "Refused",
    "RemediationResult",
    "Remedy",
    "RemedyAction",
    "Report",
    "RunRecord",
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
    "compare",
    "decode_answer",
    "doctor",
    "export",
    "failure_status",
    "load_plan",
    "plan",
    "plan_blockers",
    "preflight_sarif",
    "registered_kinds",
    "remediate",
    "render_reports",
    "run",
    "run_batch",
    "terminal_text",
    "verify_evidence",
]

audit = _audit
remediate = _remediate
run = _run
