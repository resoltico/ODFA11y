# SPDX-License-Identifier: AGPL-3.0-only
"""Typed findings, rules and machine-readable rendering."""

from odfa11y.report.json import render_json
from odfa11y.report.model import Finding, Location, Report, ReportKind, exit_status
from odfa11y.report.sarif import SarifOptions, preflight_sarif, render_sarif
from odfa11y.rules import registry as rules
from odfa11y.rules.registry import RULES, Rule, Severity

__all__ = [
    "RULES",
    "Finding",
    "Location",
    "Report",
    "ReportKind",
    "Rule",
    "SarifOptions",
    "Severity",
    "exit_status",
    "preflight_sarif",
    "render_json",
    "render_sarif",
    "rules",
]
