# SPDX-License-Identifier: MPL-2.0
"""ODFA11y's application API: explicit decisions, guarded workflows and typed results."""

from odfa11y.application import (
    AuditFailure,
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
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.audit import plan_blockers
from odfa11y.batch import BatchRecord
from odfa11y.decisions import Decision, DecisionKind, DecisionScope, OpenDecision, decode_answer
from odfa11y.errors import OdfA11yError, OutputError, PlanError, ReportError, ToolNotFoundError
from odfa11y.native.export import DEFAULT_TIMEOUT_SECONDS
from odfa11y.native.process import validate_timeout
from odfa11y.plans import Plan, PlanHeader, SourceBinding, load_plan, registered_kinds
from odfa11y.progress import ProgressEvent, ProgressObserver, StageName, StepName, StepState
from odfa11y.records import DoctorRecord
from odfa11y.remediate import RemediationResult
from odfa11y.report import FORMATS, Location, Report, preflight_sarif, render_reports, terminal_text
from odfa11y.run.profiles import DEFAULT_PROFILE, PROFILES, Profile, profile_named
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.status import ExitStatus, failure_status
from odfa11y.version import __version__

__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_TIMEOUT_SECONDS",
    "FORMATS",
    "PROFILES",
    "AuditFailure",
    "AuditInput",
    "AuditRun",
    "BatchRecord",
    "ComparisonResult",
    "Decision",
    "DecisionKind",
    "DecisionScope",
    "DoctorRecord",
    "ExitStatus",
    "ExportResult",
    "Location",
    "NativeTools",
    "OdfA11yError",
    "OpenDecision",
    "OutputError",
    "Plan",
    "PlanError",
    "PlanHeader",
    "PlanResult",
    "Profile",
    "ProgressEvent",
    "ProgressObserver",
    "RemediationResult",
    "Report",
    "ReportError",
    "RunRecord",
    "SourceBinding",
    "StageName",
    "StageResult",
    "StepName",
    "StepState",
    "ToolNotFoundError",
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
    "profile_named",
    "registered_kinds",
    "remediate",
    "render_reports",
    "run",
    "run_batch",
    "terminal_text",
    "validate_timeout",
    "verify_evidence",
]

audit = _audit
remediate = _remediate
run = _run
