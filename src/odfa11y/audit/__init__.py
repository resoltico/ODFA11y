# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only ODF accessibility audit and configuration templates."""

from odfa11y.audit.engine import BLOCKING_RULES, audit_odf
from odfa11y.audit.plan import plan_blockers, prepare_plan

__all__ = ["BLOCKING_RULES", "audit_odf", "plan_blockers", "prepare_plan"]
