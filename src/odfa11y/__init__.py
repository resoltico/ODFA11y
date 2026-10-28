# SPDX-License-Identifier: MPL-2.0
"""ODFA11y's application API: explicit decisions, guarded workflows and typed results."""

from .application import (
    AuditFailure,
    AuditInput,
    AuditRun,
    ComparisonResult,
    ExportResult,
    PlanResult,
    VerificationResult,
    audit,
    compare,
    doctor,
    export,
    plan,
    remediate,
    run,
    run_batch,
    verify_evidence,
)
from .batch import BatchRecord
from .decisions import Decision, DecisionKind, DecisionScope, OpenDecision, decode_answer
from .errors import OdfA11yError, OutputError, PlanError, ReportError, ToolNotFoundError
from .native.export import DEFAULT_TIMEOUT_SECONDS
from .native.process import validate_timeout
from .outcomes import (
    ExitStatus,
    ProgressEvent,
    ProgressObserver,
    StageName,
    StepName,
    StepState,
    failure_status,
)
from .pipeline.profiles import DEFAULT_PROFILE, PROFILES, Profile, profile_named
from .pipeline.record import RunRecord, StageResult
from .plans import Plan, PlanHeader, SourceBinding, load_plan, registered_kinds
from .records import DoctorRecord
from .remediation import RemediationResult
from .report import FORMATS, Location, Report, preflight_sarif, render_reports, terminal_text
from .source_audit import plan_blockers
from .tools import Tools
from .version import __version__

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
