# SPDX-License-Identifier: MPL-2.0
"""The nine application use cases and their immutable result contracts."""

from odfa11y.application.audit import AuditInput, AuditResult, audit
from odfa11y.application.batch import batch
from odfa11y.application.compare import ComparisonResult, compare
from odfa11y.application.doctor import DoctorResult, doctor
from odfa11y.application.export import ExportResult, export
from odfa11y.application.native import NativeTools
from odfa11y.application.plan import PlanResult, plan
from odfa11y.application.remediate import remediate
from odfa11y.application.run import run
from odfa11y.application.tools import Tools
from odfa11y.application.verify_evidence import VerificationResult, verify_evidence
from odfa11y.batch.record import BatchRecord
from odfa11y.remediate import RemediationResult
from odfa11y.run.record import RunRecord

__all__ = [
    "AuditInput",
    "AuditResult",
    "BatchRecord",
    "ComparisonResult",
    "DoctorResult",
    "ExportResult",
    "NativeTools",
    "PlanResult",
    "RemediationResult",
    "RunRecord",
    "Tools",
    "VerificationResult",
    "audit",
    "batch",
    "compare",
    "doctor",
    "export",
    "plan",
    "remediate",
    "run",
    "verify_evidence",
]
