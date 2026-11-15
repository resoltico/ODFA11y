# SPDX-License-Identifier: MPL-2.0
"""Rules, findings and report rendering shared by every check."""

from odfa11y.report.model import Finding, Location, Report, ReportKind
from odfa11y.report.render import FORMATS, exit_status, render_reports
from odfa11y.report.sarif import preflight_sarif
from odfa11y.report.terminal import terminal_text
from odfa11y.rules import registry as rules
from odfa11y.rules.registry import RULES, Rule, Severity

__all__ = [
    "FORMATS",
    "RULES",
    "Finding",
    "Location",
    "Report",
    "ReportKind",
    "Rule",
    "Severity",
    "exit_status",
    "preflight_sarif",
    "render_reports",
    "rules",
    "terminal_text",
]
