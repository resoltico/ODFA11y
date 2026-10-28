# SPDX-License-Identifier: MPL-2.0
"""The assurance workflow: audit, remediate, export, validate, compare, keep evidence."""

from odfa11y.native.export import DEFAULT_TIMEOUT_SECONDS
from odfa11y.outcomes import PIPELINE_STAGES

from .comparison import compare_documents, is_pdf
from .diagnostics import inspect_tools
from .inspection import audit_document
from .native import NativeOptions, export_document
from .profiles import DEFAULT_PROFILE, PROFILES, Profile, profile_named
from .record import PipelineOptions, RunRecord, StageResult
from .run import run_pipeline

__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_TIMEOUT_SECONDS",
    "PIPELINE_STAGES",
    "PROFILES",
    "NativeOptions",
    "PipelineOptions",
    "Profile",
    "RunRecord",
    "StageResult",
    "audit_document",
    "compare_documents",
    "export_document",
    "inspect_tools",
    "is_pdf",
    "profile_named",
    "run_pipeline",
]
